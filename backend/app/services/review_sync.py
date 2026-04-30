from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.importers import steam_api_review_to_values
from app.models import SteamReview, SyncJob
from app.repositories import SteamReviewRepository

CHINA_TZ = ZoneInfo("Asia/Shanghai")


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
    ) -> dict[str, Any]:
        ...

    async def close(self) -> None:
        ...


@dataclass(frozen=True)
class ReviewSyncOptions:
    app_id: int
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
        scraper_factory: Callable[[], CommentScraperProtocol] | None = None,
    ) -> None:
        self.session = session
        self.repository = SteamReviewRepository(session)
        self.scraper_factory = scraper_factory or create_comment_scraper

    async def sync_reviews(self, options: ReviewSyncOptions) -> ReviewSyncResult:
        if options.sync_job_id is not None:
            sync_job = await self.session.get(SyncJob, options.sync_job_id)
            if sync_job is None:
                raise ValueError(f"Sync job not found: {options.sync_job_id}")
            sync_job.status = "running"
            sync_job.started_at = datetime.now(tz=CHINA_TZ)
        else:
            sync_job = SyncJob(
                app_id=options.app_id,
                job_type="steam_review_sync",
                source_type="steam_api",
                status="running",
                requested_limit=options.limit,
                started_at=datetime.now(tz=CHINA_TZ),
            )
            self.session.add(sync_job)
        await self.session.flush()

        inserted = 0
        updated = 0
        skipped = 0
        query_summary: dict[str, Any] = {}
        scraper = self.scraper_factory()
        latest_review = await self.get_latest_review(options.app_id)
        latest_review_created_at = latest_review.timestamp_created if latest_review else None
        since_timestamp = datetime_to_epoch_seconds(
            latest_review_created_at,
            source_type=latest_review.source_type if latest_review else None,
        )

        try:
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
            )
            query_summary = result.get("query_summary") or {}
            query_summary["local_latest_review_created_at"] = (
                latest_review_created_at.isoformat() if latest_review_created_at else None
            )
            query_summary["since_timestamp"] = since_timestamp

            for review in result.get("reviews", []):
                values = steam_api_review_to_values(options.app_id, review)
                upsert_result = await self.repository.upsert_review(values)
                inserted += upsert_result.inserted
                updated += upsert_result.updated
                skipped += upsert_result.skipped

            sync_job.status = "success"
            sync_job.inserted_count = inserted
            sync_job.updated_count = updated
            sync_job.skipped_count = skipped
            sync_job.finished_at = datetime.now(tz=CHINA_TZ)
            await self.session.commit()
        except Exception as exc:
            sync_job.status = "failed"
            sync_job.inserted_count = inserted
            sync_job.updated_count = updated
            sync_job.skipped_count = skipped
            sync_job.error_message = str(exc)
            sync_job.finished_at = datetime.now(tz=CHINA_TZ)
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


def create_comment_scraper() -> CommentScraperProtocol:
    from src.scrapers.comment_scraper import CommentScraper

    return CommentScraper()


def datetime_to_epoch_seconds(value: datetime | None, source_type: str | None = None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        timezone = CHINA_TZ if source_type == "csv" else UTC
        value = value.replace(tzinfo=timezone)
    return int(value.timestamp())
