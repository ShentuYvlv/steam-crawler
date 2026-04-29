from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.importers import steam_api_review_to_values
from app.models import SyncJob
from app.repositories import SteamReviewRepository

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class CommentScraperProtocol(Protocol):
    async def scrape_app_comments(
        self,
        app_id: int,
        limit: int | None = None,
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

        try:
            result = await scraper.scrape_app_comments(
                app_id=options.app_id,
                limit=options.limit,
                language=options.language,
                filter_type=options.filter,
                review_type=options.review_type,
                purchase_type=options.purchase_type,
                num_per_page=options.per_page,
                use_review_quality=options.use_review_quality,
            )
            query_summary = result.get("query_summary") or {}

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


def create_comment_scraper() -> CommentScraperProtocol:
    from src.scrapers.comment_scraper import CommentScraper

    return CommentScraper()
