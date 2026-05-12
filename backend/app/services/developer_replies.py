from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.config import REPO_ROOT, get_settings
from app.core.error_utils import format_exception_message
from app.models import DeveloperReply, OperationLog, ReplyDraft, SteamReview

CHINA_TZ = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)


class SteamDeveloperReplyClient(Protocol):
    async def set_developer_response(
        self,
        recommendation_id: str,
        response_text: str,
    ) -> dict[str, Any]: ...

    async def get_transport_diagnostics(self) -> dict[str, Any]: ...

    async def close(self) -> None: ...


class DeveloperReplyError(RuntimeError):
    def __init__(self, message: str, record_id: int | None = None) -> None:
        super().__init__(message)
        self.record_id = record_id


class DeveloperReplyService:
    def __init__(
        self,
        session: AsyncSession,
        client_factory: Callable[[], SteamDeveloperReplyClient] | None = None,
    ) -> None:
        self.session = session
        self.client_factory = client_factory or create_steam_reply_client
        self.last_transport_diagnostics: dict[str, Any] | None = None

    def _collect_transport_metadata(
        self,
        client: SteamDeveloperReplyClient | None,
    ) -> dict[str, Any]:
        metadata = dict(self.last_transport_diagnostics or {})
        if client is not None:
            metadata_getter = getattr(client, "get_last_request_metadata", None)
            if callable(metadata_getter):
                try:
                    metadata.update(metadata_getter())
                except Exception:
                    pass
        return metadata

    def _build_send_error_message(
        self,
        exc: Exception,
        client: SteamDeveloperReplyClient | None,
    ) -> str:
        metadata = self._collect_transport_metadata(client)
        if isinstance(exc, httpx.ConnectTimeout):
            if metadata.get("proxy_enabled"):
                return (
                    "ConnectTimeout: 无法连接 steamcommunity.com。"
                    f" 当前发送链路使用代理模式 {metadata.get('proxy_mode')}"
                    f" ({metadata.get('proxy_scheme') or 'unknown'}:{metadata.get('proxy_port') or 'n/a'})，"
                    " 请检查代理可用性，或关闭代理后验证服务器直连。"
                )
            return (
                "ConnectTimeout: 服务器无法连接 steamcommunity.com。"
                " 请检查 DNS 解析、IPv6/IPv4 连通性、服务器出口网络，或为发送链路配置代理。"
            )
        return format_exception_message(exc)

    async def send_reply(
        self,
        review_id: int,
        *,
        confirmed: bool,
        draft_id: int | None = None,
        content: str | None = None,
        sent_by_user_id: int | None = None,
    ) -> DeveloperReply:
        record = await self.queue_reply(
            review_id,
            confirmed=confirmed,
            draft_id=draft_id,
            content=content,
            sent_by_user_id=sent_by_user_id,
        )
        return await self.perform_send(record.id)

    async def queue_reply(
        self,
        review_id: int,
        *,
        confirmed: bool,
        draft_id: int | None = None,
        content: str | None = None,
        sent_by_user_id: int | None = None,
    ) -> DeveloperReply:
        if not confirmed:
            raise DeveloperReplyError("Sending a Steam developer reply requires confirmation")

        review = await self.session.get(SteamReview, review_id)
        if review is None:
            raise DeveloperReplyError("Review not found")

        blocking_record = await self._find_blocking_record(review.id)
        if blocking_record is not None and blocking_record.status == "pending":
            raise DeveloperReplyError("Reply send already in progress", blocking_record.id)
        if review.reply_status == "sending":
            raise DeveloperReplyError("Reply send already in progress", blocking_record.id if blocking_record else None)
        if review.reply_status == "replied":
            raise DeveloperReplyError("Review reply already sent", blocking_record.id if blocking_record else None)
        if blocking_record is not None and blocking_record.status == "sent":
            raise DeveloperReplyError("Review reply already sent", blocking_record.id)

        draft = await self._resolve_draft(review.id, draft_id)
        reply_content = (content or (draft.content if draft else "")).strip()
        if not reply_content:
            raise DeveloperReplyError("Reply content is required")

        now = datetime.now(tz=CHINA_TZ)
        if draft is not None:
            draft.content = reply_content
            draft.status = "sending"
            draft.error_message = None
            draft.reviewed_by_user_id = sent_by_user_id
            draft.reviewed_at = now
        review.reply_status = "sending"

        record = DeveloperReply(
            review_id=review.id,
            draft_id=draft.id if draft else None,
            recommendation_id=review.recommendation_id,
            content=reply_content,
            status="pending",
            sent_by_user_id=sent_by_user_id,
        )
        self.session.add(record)
        self.session.add(
            OperationLog(
                action="developer_reply_queued",
                user_id=sent_by_user_id,
                target_type="developer_reply",
                target_id=str(review.id),
                details=json.dumps(
                    {"review_id": review.id, "recommendation_id": review.recommendation_id},
                    ensure_ascii=False,
                ),
            )
        )
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def perform_send(self, record_id: int) -> DeveloperReply:
        record = await self.session.get(DeveloperReply, record_id)
        if record is None:
            raise DeveloperReplyError("Reply record not found", record_id)
        if record.status == "sent":
            await self.session.refresh(record)
            return record
        if record.status != "pending":
            raise DeveloperReplyError("Reply send is not pending", record.id)

        review = await self.session.get(SteamReview, record.review_id)
        if review is None:
            record.status = "failed"
            record.error_message = "Review not found"
            await self.session.commit()
            raise DeveloperReplyError("Review not found", record.id)

        draft = await self.session.get(ReplyDraft, record.draft_id) if record.draft_id is not None else None

        client: SteamDeveloperReplyClient | None = None
        try:
            client = self.client_factory()
            diagnostics_getter = getattr(client, "get_transport_diagnostics", None)
            if callable(diagnostics_getter):
                self.last_transport_diagnostics = await diagnostics_getter()
            steam_result = await client.set_developer_response(
                recommendation_id=review.recommendation_id,
                response_text=record.content,
            )
            if not steam_result.get("success"):
                raise DeveloperReplyError(json.dumps(steam_result, ensure_ascii=False), record.id)

            now = datetime.now(tz=CHINA_TZ)
            record.status = "sent"
            record.error_message = None
            record.steam_response = json.dumps(steam_result.get("response"), ensure_ascii=False)
            record.sent_at = now
            review.processing_status = "completed"
            review.reply_status = "replied"
            review.developer_response = record.content
            review.developer_response_created_at = now
            if draft is not None:
                draft.status = "sent"
                draft.error_message = None
                if draft.reviewed_at is None:
                    draft.reviewed_at = now
            self.session.add(
                OperationLog(
                    action="developer_reply_sent",
                    user_id=record.sent_by_user_id,
                    target_type="developer_reply",
                    target_id=str(record.id),
                    details=json.dumps(
                        {"review_id": review.id, "recommendation_id": review.recommendation_id},
                        ensure_ascii=False,
                    ),
                )
            )
            await self.session.commit()
            await self.session.refresh(record)
            return record
        except Exception as exc:
            transport_metadata = self._collect_transport_metadata(client)
            message = self._build_send_error_message(exc, client)
            record.status = "failed"
            record.error_message = message
            review.reply_status = "send_failed"
            if draft is not None:
                draft.status = "send_failed"
                draft.error_message = message
            await self.session.commit()
            logger.exception(
                "Steam developer reply send failed for record_id=%s review_id=%s transport=%s",
                record.id,
                review.id,
                transport_metadata,
            )
            raise DeveloperReplyError(message, record.id) from exc
        finally:
            if client is not None:
                await client.close()

    async def _find_blocking_record(self, review_id: int) -> DeveloperReply | None:
        pending_result = await self.session.execute(
            select(DeveloperReply)
            .where(
                DeveloperReply.review_id == review_id,
                DeveloperReply.status == "pending",
            )
            .order_by(desc(DeveloperReply.created_at), desc(DeveloperReply.id))
            .limit(1)
        )
        pending_record = pending_result.scalar_one_or_none()
        if pending_record is not None:
            return pending_record

        sent_result = await self.session.execute(
            select(DeveloperReply)
            .where(
                DeveloperReply.review_id == review_id,
                DeveloperReply.status == "sent",
            )
            .order_by(desc(DeveloperReply.sent_at), desc(DeveloperReply.id))
            .limit(1)
        )
        return sent_result.scalar_one_or_none()

    async def _resolve_draft(self, review_id: int, draft_id: int | None) -> ReplyDraft | None:
        if draft_id is not None:
            draft = await self.session.get(ReplyDraft, draft_id)
            if draft is None or draft.review_id != review_id:
                raise DeveloperReplyError("Reply draft not found")
            return draft

        result = await self.session.execute(
            select(ReplyDraft)
            .where(ReplyDraft.review_id == review_id)
            .order_by(desc(ReplyDraft.created_at), desc(ReplyDraft.id))
            .limit(1)
        )
        return result.scalar_one_or_none()


def create_steam_reply_client() -> SteamDeveloperReplyClient:
    from src.scrapers.comment_reply import DeveloperReplyClient, load_cookie_header

    settings = get_settings()
    cookie_file = resolve_cookie_file_path(settings.steam_cookie_file)
    if not cookie_file.exists():
        raise DeveloperReplyError(
            "Cookie file does not exist: "
            f"{settings.steam_cookie_file}. "
            f"Resolved path: {cookie_file}"
        )

    cookie_header = load_cookie_header(cookie_file)
    return DeveloperReplyClient(
        cookie_header=cookie_header,
        proxy_url=settings.steam_reply_proxy_url or None,
        proxy_direct_fallback=settings.steam_reply_proxy_direct_fallback,
    )


def resolve_cookie_file_path(path_value: str) -> Path:
    raw_value = path_value.strip()
    configured = Path(raw_value).expanduser()
    candidates: list[Path] = [configured]

    if not configured.is_absolute():
        candidates.append((REPO_ROOT / configured).resolve())

    if raw_value.startswith("/app/"):
        docker_mapped = (REPO_ROOT / raw_value.removeprefix("/app/")).resolve()
        candidates.append(docker_mapped)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate

    return candidates[-1] if candidates else configured


async def process_pending_reply_send(record_id: int) -> None:
    async with AsyncSessionLocal() as session:
        service = DeveloperReplyService(session)
        try:
            await service.perform_send(record_id)
        except DeveloperReplyError as exc:
            logger.warning(
                "Background Steam developer reply send failed for record_id=%s: %s",
                record_id,
                exc,
            )
            return


async def recover_pending_reply_sends() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DeveloperReply.id)
            .where(DeveloperReply.status == "pending")
            .order_by(DeveloperReply.created_at, DeveloperReply.id)
        )
        record_ids = list(result.scalars().all())

    for record_id in record_ids:
        asyncio.create_task(process_pending_reply_send(record_id))
