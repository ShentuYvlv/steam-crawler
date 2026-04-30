from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import DeveloperReply, OperationLog, ReplyDraft, SteamReview

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class SteamDeveloperReplyClient(Protocol):
    async def set_developer_response(
        self,
        recommendation_id: str,
        response_text: str,
    ) -> dict[str, Any]: ...

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

    async def send_reply(
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

        draft = await self._resolve_draft(review.id, draft_id)
        reply_content = (content or (draft.content if draft else "")).strip()
        if not reply_content:
            raise DeveloperReplyError("Reply content is required")

        record = DeveloperReply(
            review_id=review.id,
            draft_id=draft.id if draft else None,
            recommendation_id=review.recommendation_id,
            content=reply_content,
            status="pending",
            sent_by_user_id=sent_by_user_id,
        )
        self.session.add(record)
        await self.session.flush()

        client: SteamDeveloperReplyClient | None = None
        try:
            client = self.client_factory()
            steam_result = await client.set_developer_response(
                recommendation_id=review.recommendation_id,
                response_text=reply_content,
            )
            if not steam_result.get("success"):
                raise DeveloperReplyError(json.dumps(steam_result, ensure_ascii=False), record.id)

            now = datetime.now(tz=CHINA_TZ)
            record.status = "sent"
            record.steam_response = json.dumps(steam_result.get("response"), ensure_ascii=False)
            record.sent_at = now
            review.reply_status = "replied"
            review.developer_response = reply_content
            review.developer_response_created_at = now
            if draft is not None:
                draft.status = "sent"
                draft.reviewed_at = now
            self.session.add(
                OperationLog(
                    action="developer_reply_sent",
                    user_id=sent_by_user_id,
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
            record.status = "failed"
            record.error_message = str(exc)
            review.reply_status = "send_failed"
            if draft is not None:
                draft.status = "send_failed"
            await self.session.commit()
            raise DeveloperReplyError(str(exc), record.id) from exc
        finally:
            if client is not None:
                await client.close()

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
    cookie_file = Path(settings.steam_cookie_file)
    if not cookie_file.exists():
        raise DeveloperReplyError(f"Cookie file does not exist: {cookie_file}")

    cookie_header = load_cookie_header(cookie_file)
    return DeveloperReplyClient(cookie_header=cookie_header)
