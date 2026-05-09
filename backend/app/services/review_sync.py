from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.utils.steam_rate_limiter import get_steam_rate_limiter
from src.utils.task_control import SteamTemporarilyUnavailableError, TaskCancelledError

from app.core.error_utils import format_exception_details, format_exception_message
from app.importers import steam_api_review_to_values
from app.models import SteamReview, SyncJob
from app.repositories import SteamReviewRepository
from app.services.task_logs import add_task_log
from app.services.task_runtime import finalize_cancelled_task

CHINA_TZ = ZoneInfo("Asia/Shanghai")
PROGRESS_LOG_INTERVAL = 500


class CommentScraperProtocol(Protocol):
    async def scrape_app_comments(
        self,
        app_id: int,
        limit: int | None = None,
        since_timestamp: int | None = None,
        language: str = "schinese",
        filter_type: str = "recent",
        review_type: str = "all",
        purchase_type: str = "all",
        num_per_page: int = 100,
        use_review_quality: bool = True,
        on_page: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        collect_reviews: bool = True,
    ) -> dict[str, Any]:
        ...

    async def close(self) -> None:
        ...


@dataclass(frozen=True)
class ReviewSyncOptions:
    app_id: int
    schedule_id: int | None = None
    schedule_name: str | None = None
    trigger_type: str = "manual"
    limit: int | None = None
    language: str = "schinese"
    filter: str = "recent"
    review_type: str = "all"
    purchase_type: str = "all"
    use_review_quality: bool = True
    per_page: int = 100
    sync_job_id: int | None = None


@dataclass(frozen=True)
class ReviewSyncResult:
    sync_job_id: int
    app_id: int
    inserted: int
    updated: int
    skipped: int
    status: str
    query_summary: dict[str, Any]


class SteamReviewSyncService:
    def __init__(
        self,
        session: AsyncSession,
        scraper_factory: Callable[..., CommentScraperProtocol] | None = None,
        *,
        cancel_event=None,
    ) -> None:
        self.session = session
        self.repository = SteamReviewRepository(session)
        self.scraper_factory = scraper_factory or create_comment_scraper
        self.cancel_event = cancel_event

    async def sync_reviews(self, options: ReviewSyncOptions) -> ReviewSyncResult:
        if options.sync_job_id is not None:
            sync_job = await self.session.get(SyncJob, options.sync_job_id)
            if sync_job is None:
                raise ValueError(f"Sync job not found: {options.sync_job_id}")
            sync_job.status = "running"
            sync_job.started_at = datetime.now(tz=CHINA_TZ)
            sync_job.finished_at = None
            sync_job.error_message = None
        else:
            sync_job = SyncJob(
                schedule_id=options.schedule_id,
                schedule_name=options.schedule_name,
                trigger_type=options.trigger_type,
                app_id=options.app_id,
                job_type="steam_review_sync",
                source_type="steam_api",
                status="running",
                requested_limit=options.limit,
                started_at=datetime.now(tz=CHINA_TZ),
            )
            self.session.add(sync_job)
        await self.session.flush()
        await self._raise_if_cancelled(sync_job)
        await add_task_log(
            self.session,
            sync_job.id,
            "开始抓取 Steam 评论",
            details={"app_id": options.app_id},
        )

        inserted = 0
        updated = 0
        skipped = 0
        query_summary: dict[str, Any] = {}
        page_callback_invoked = False
        next_progress_log_threshold = PROGRESS_LOG_INTERVAL
        scraper = self._create_scraper()
        latest_review = await self.get_latest_review(options.app_id)
        latest_review_created_at = latest_review.timestamp_created if latest_review else None
        since_timestamp = datetime_to_epoch_seconds(
            latest_review_created_at,
            source_type=latest_review.source_type if latest_review else None,
        )
        sync_mode = "incremental" if since_timestamp is not None else "initial"
        await add_task_log(
            self.session,
            sync_job.id,
            "已确定增量同步起点",
            details={
                "latest_review_created_at": (
                    latest_review_created_at.isoformat() if latest_review_created_at else None
                ),
                "since_timestamp": since_timestamp,
            },
        )
        await add_task_log(
            self.session,
            sync_job.id,
            "Steam 限流状态",
            details={
                "sync_mode": sync_mode,
                **(await get_steam_rate_limiter().snapshot()),
            },
        )

        await self.session.commit()

        try:
            async def persist_reviews_batch(
                reviews_batch: list[dict[str, Any]],
                *,
                page_index: int | None = None,
                total_review_count: int | None = None,
            ) -> None:
                nonlocal inserted, updated, skipped, page_callback_invoked, next_progress_log_threshold
                page_callback_invoked = True
                await self._raise_if_cancelled(sync_job)
                for review in reviews_batch:
                    await self._raise_if_cancelled(sync_job)
                    values = steam_api_review_to_values(options.app_id, review)
                    upsert_result = await self.repository.upsert_review(values)
                    inserted += upsert_result.inserted
                    updated += upsert_result.updated
                    skipped += upsert_result.skipped

                sync_job.inserted_count = inserted
                sync_job.updated_count = updated
                sync_job.skipped_count = skipped

                if (
                    total_review_count is not None
                    and total_review_count >= next_progress_log_threshold
                ):
                    await add_task_log(
                        self.session,
                        sync_job.id,
                        "评论同步进行中",
                        details={
                            "page_index": page_index,
                            "fetched": total_review_count,
                            "inserted": inserted,
                            "updated": updated,
                            "skipped": skipped,
                            "sync_mode": sync_mode,
                        },
                    )
                    while total_review_count >= next_progress_log_threshold:
                        next_progress_log_threshold += PROGRESS_LOG_INTERVAL

                await self.session.commit()

            async def handle_page(page_payload: dict[str, Any]) -> None:
                await persist_reviews_batch(
                    list(page_payload.get("reviews", [])),
                    page_index=(
                        int(page_payload["page_index"])
                        if page_payload.get("page_index") is not None
                        else None
                    ),
                    total_review_count=(
                        int(page_payload["total_review_count"])
                        if page_payload.get("total_review_count") is not None
                        else None
                    ),
                )

            await self._raise_if_cancelled(sync_job)
            result = await scraper.scrape_app_comments(
                app_id=options.app_id,
                limit=options.limit,
                since_timestamp=since_timestamp,
                language=options.language,
                filter_type=options.filter,
                review_type=options.review_type,
                purchase_type=options.purchase_type,
                num_per_page=options.per_page,
                use_review_quality=options.use_review_quality,
                on_page=handle_page,
                collect_reviews=False,
            )
            query_summary = result.get("query_summary") or {}
            query_summary["local_latest_review_created_at"] = (
                latest_review_created_at.isoformat() if latest_review_created_at else None
            )
            query_summary["since_timestamp"] = since_timestamp

            if not page_callback_invoked:
                await persist_reviews_batch(
                    list(result.get("reviews", [])),
                    total_review_count=(
                        int(result["review_count"]) if result.get("review_count") is not None else None
                    ),
                )

            sync_job.status = "success"
            sync_job.inserted_count = inserted
            sync_job.updated_count = updated
            sync_job.skipped_count = skipped
            sync_job.finished_at = datetime.now(tz=CHINA_TZ)
            await add_task_log(
                self.session,
                sync_job.id,
                "评论同步完成",
                details={
                    "fetched": result.get("review_count", inserted + updated + skipped),
                    "inserted": inserted,
                    "updated": updated,
                    "skipped": skipped,
                    "sync_mode": sync_mode,
                    **(await get_steam_rate_limiter().snapshot()),
                },
            )
            await self.session.commit()
        except TaskCancelledError:
            sync_job.inserted_count = inserted
            sync_job.updated_count = updated
            sync_job.skipped_count = skipped
            await finalize_cancelled_task(
                self.session,
                sync_job,
                message="评论同步已取消",
                details={
                    "inserted": inserted,
                    "updated": updated,
                    "skipped": skipped,
                    "sync_mode": sync_mode,
                },
            )
            await self.session.commit()
            return ReviewSyncResult(
                sync_job_id=sync_job.id,
                app_id=options.app_id,
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                status=sync_job.status,
                query_summary=query_summary,
            )
        except Exception as exc:
            limiter = get_steam_rate_limiter()
            if limiter.is_availability_error(exc):
                sync_job.status = "waiting"
                sync_job.inserted_count = inserted
                sync_job.updated_count = updated
                sync_job.skipped_count = skipped
                sync_job.error_message = format_exception_message(exc)
                await add_task_log(
                    self.session,
                    sync_job.id,
                    "Steam 当前不可用，任务等待探针恢复",
                    level="warning",
                    details={
                        **format_exception_details(exc),
                        "sync_mode": sync_mode,
                        "steam_rate_limit": await limiter.snapshot(),
                    },
                )
                await self.session.commit()
                raise SteamTemporarilyUnavailableError(format_exception_message(exc)) from exc
            sync_job.status = "failed"
            sync_job.inserted_count = inserted
            sync_job.updated_count = updated
            sync_job.skipped_count = skipped
            sync_job.error_message = format_exception_message(exc)
            sync_job.finished_at = datetime.now(tz=CHINA_TZ)
            await add_task_log(
                self.session,
                sync_job.id,
                "评论同步失败",
                level="error",
                details={
                    **format_exception_details(exc),
                    "sync_mode": sync_mode,
                    "steam_rate_limit": await get_steam_rate_limiter().snapshot(),
                },
            )
            await self.session.commit()
            raise
        finally:
            await scraper.close()

        return ReviewSyncResult(
            sync_job_id=sync_job.id,
            app_id=options.app_id,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            status=sync_job.status,
            query_summary=query_summary,
        )

    async def get_latest_review(self, app_id: int) -> SteamReview | None:
        result = await self.session.execute(
            select(SteamReview)
            .where(
                SteamReview.app_id == app_id,
                SteamReview.timestamp_created.is_not(None),
            )
            .order_by(desc(SteamReview.timestamp_created), desc(SteamReview.id))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _raise_if_cancelled(self, sync_job: SyncJob) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise TaskCancelledError()
        current_task = await self.session.get(SyncJob, sync_job.id)
        if current_task is not None and current_task.status in {"cancel_requested", "cancelled"}:
            raise TaskCancelledError()

    def _create_scraper(self) -> CommentScraperProtocol:
        try:
            return self.scraper_factory(self.cancel_event)
        except TypeError:
            return self.scraper_factory()


def create_comment_scraper(cancel_event=None) -> CommentScraperProtocol:
    from src.scrapers.comment_scraper import CommentScraper

    return CommentScraper(stop_event=cancel_event)


def datetime_to_epoch_seconds(value: datetime | None, source_type: str | None = None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        timezone = CHINA_TZ if source_type == "csv" else UTC
        value = value.replace(tzinfo=timezone)
    return int(value.timestamp())
