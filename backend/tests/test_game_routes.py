from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.main import app
from app.models import Base, SteamGame, SteamReview


async def test_games_route_returns_games_with_review_counts() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add_all(
            [
                SteamGame(app_id=3350200, name="情感反诈模拟器"),
                SteamGame(app_id=4000000, name="备用游戏"),
            ]
        )
        seed_session.add_all(
            [
                SteamReview(
                    app_id=3350200,
                    recommendation_id="a-1",
                    review_text="评论1",
                    sync_type="stock",
                    source_type="csv",
                ),
                SteamReview(
                    app_id=3350200,
                    recommendation_id="a-2",
                    review_text="评论2",
                    sync_type="stock",
                    source_type="csv",
                ),
                SteamReview(
                    app_id=4000000,
                    recommendation_id="b-1",
                    review_text="评论3",
                    sync_type="stock",
                    source_type="csv",
                ),
            ]
        )
        await seed_session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/games")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["app_id"] == 3350200
    assert payload[0]["review_count"] == 2
    assert payload[1]["app_id"] == 4000000
    assert payload[1]["review_count"] == 1
