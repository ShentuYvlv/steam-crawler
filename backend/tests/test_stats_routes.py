from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.main import app
from app.models import Base, DeveloperReply, SteamGame, SteamReview


async def test_stats_overview_and_timeseries() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add(SteamGame(app_id=3350200, name="test game"))
        review = SteamReview(
            app_id=3350200,
            recommendation_id="1001",
            review_text="测试评论",
            voted_up=True,
            votes_up=1,
            votes_funny=0,
            comment_count=0,
            timestamp_created=datetime.now(tz=UTC),
            sync_type="stock",
            source_type="csv",
            processing_status="pending",
            reply_status="replied",
        )
        seed_session.add(review)
        await seed_session.flush()
        seed_session.add(
            DeveloperReply(
                review_id=review.id,
                recommendation_id=review.recommendation_id,
                content="回复",
                status="sent",
                sent_at=datetime.now(tz=UTC),
            )
        )
        await seed_session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            overview_response = await client.get("/api/stats/overview")
            timeseries_response = await client.get("/api/stats/timeseries?days=3")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert overview_response.status_code == 200
    assert overview_response.json()["total_reviews"] == 1
    assert overview_response.json()["positive_rate"] == 1
    assert timeseries_response.status_code == 200
    assert len(timeseries_response.json()["items"]) == 3
