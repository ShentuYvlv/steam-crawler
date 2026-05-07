from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.utils.task_control import TaskCancelledError

from app.models import Base, SteamReview, SyncJob, TaskLog
from app.services.review_sync import ReviewSyncOptions, SteamReviewSyncService

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class FakeCommentScraper:
    def __init__(self) -> None:
        self.closed = False
        self.kwargs = None

    async def scrape_app_comments(self, **kwargs):
        assert kwargs["app_id"] == 3350200
        assert kwargs["filter_type"] == "recent"
        self.kwargs = kwargs
        return {
            "app_id": 3350200,
            "query_summary": {"total_reviews": 1},
            "reviews": [
                {
                    "recommendationid": "224190513",
                    "author": {
                        "steamid": "76561199114484931",
                        "personaname": "tester",
                        "profile_url": "https://steamcommunity.com/profiles/76561199114484931/",
                        "num_games_owned": 246,
                        "num_reviews": 7,
                        "playtime_forever": 313,
                        "playtime_last_two_weeks": 265,
                        "playtime_at_review": 313,
                        "last_played": 1777181180,
                    },
                    "language": "schinese",
                    "review": "测试评论",
                    "timestamp_created": 1777258404,
                    "timestamp_updated": 1777258793,
                    "voted_up": False,
                    "votes_up": 3,
                    "votes_funny": 0,
                    "weighted_vote_score": "0.565217375755310059",
                    "comment_count": 0,
                    "steam_purchase": False,
                    "received_for_free": False,
                    "refunded": False,
                    "written_during_early_access": False,
                }
            ],
        }

    async def close(self) -> None:
        self.closed = True


class EmptyMessageScraper:
    async def scrape_app_comments(self, **kwargs):
        raise RuntimeError()

    async def close(self) -> None:
        return None


class CancelledScraper:
    async def scrape_app_comments(self, **kwargs):
        raise TaskCancelledError()

    async def close(self) -> None:
        return None


async def test_review_sync_service_upserts_reviews_and_records_job() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        service = SteamReviewSyncService(session, scraper_factory=FakeCommentScraper)
        result = await service.sync_reviews(ReviewSyncOptions(app_id=3350200, limit=1))

        reviews = (await session.execute(select(SteamReview))).scalars().all()
        jobs = (await session.execute(select(SyncJob))).scalars().all()

    await engine.dispose()

    assert result.inserted == 1
    assert result.updated == 0
    assert result.status == "success"
    assert len(reviews) == 1
    assert reviews[0].recommendation_id == "224190513"
    assert reviews[0].sync_type == "incremental"
    assert reviews[0].source_type == "steam_api"
    assert len(jobs) == 1
    assert jobs[0].status == "success"


async def test_review_sync_service_uses_latest_local_review_timestamp() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    scraper = FakeCommentScraper()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            SteamReview(
                app_id=3350200,
                recommendation_id="existing",
                review_text="existing review",
                timestamp_created=datetime.fromtimestamp(1777250000, tz=CHINA_TZ),
                sync_type="stock",
                source_type="csv",
            )
        )
        await session.commit()

        service = SteamReviewSyncService(session, scraper_factory=lambda: scraper)
        result = await service.sync_reviews(ReviewSyncOptions(app_id=3350200))

    await engine.dispose()

    assert result.status == "success"
    assert scraper.kwargs is not None
    assert scraper.kwargs["limit"] is None
    assert scraper.kwargs["since_timestamp"] == 1777250000


async def test_review_sync_service_records_non_empty_failure_message_and_traceback() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        service = SteamReviewSyncService(session, scraper_factory=EmptyMessageScraper)

        try:
            await service.sync_reviews(ReviewSyncOptions(app_id=3350200))
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected RuntimeError to be raised")

        job = (await session.execute(select(SyncJob))).scalar_one()
        logs = (await session.execute(select(TaskLog).order_by(TaskLog.id))).scalars().all()

    await engine.dispose()

    assert job.status == "failed"
    assert job.error_message == "RuntimeError"
    assert logs[-1].level == "error"
    assert logs[-1].details is not None
    assert logs[-1].details["error"] == "RuntimeError"
    assert logs[-1].details["exception_type"] == "RuntimeError"
    assert "RuntimeError" in logs[-1].details["traceback"]


async def test_review_sync_service_marks_task_cancelled() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        service = SteamReviewSyncService(session, scraper_factory=lambda _: CancelledScraper())
        result = await service.sync_reviews(ReviewSyncOptions(app_id=3350200))

        job = (await session.execute(select(SyncJob))).scalar_one()
        logs = (await session.execute(select(TaskLog).order_by(TaskLog.id))).scalars().all()

    await engine.dispose()

    assert result.status == "cancelled"
    assert job.status == "cancelled"
    assert logs[-1].message == "评论同步已取消"
