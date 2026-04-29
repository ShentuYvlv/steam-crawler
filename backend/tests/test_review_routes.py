from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.main import app
from app.models import Base, SteamGame, SteamReview


async def test_review_list_filters_and_status_updates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add(SteamGame(app_id=3350200, name="test game"))
        seed_session.add_all(
            [
                SteamReview(
                    app_id=3350200,
                    recommendation_id="1001",
                    steam_id="steam-a",
                    review_text="这是一条差评，需要处理",
                    voted_up=False,
                    votes_up=10,
                    votes_funny=1,
                    comment_count=0,
                    playtime_forever=7.5,
                    timestamp_created=datetime(2026, 4, 28, 12, tzinfo=UTC),
                    sync_type="stock",
                    source_type="csv",
                    processing_status="pending",
                    reply_status="none",
                ),
                SteamReview(
                    app_id=3350200,
                    recommendation_id="1002",
                    steam_id="steam-b",
                    review_text="这是一条好评",
                    voted_up=True,
                    votes_up=1,
                    votes_funny=0,
                    comment_count=0,
                    playtime_forever=1.0,
                    timestamp_created=datetime(2026, 4, 27, 12, tzinfo=UTC),
                    sync_type="stock",
                    source_type="csv",
                    processing_status="pending",
                    reply_status="none",
                ),
            ]
        )
        await seed_session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            list_response = await client.get(
                "/api/reviews",
                params={
                    "app_id": 3350200,
                    "voted_up": False,
                    "keyword": "差评",
                    "sort_by": "votes_up",
                    "sort_order": "desc",
                },
            )
            detail_response = await client.get("/api/reviews/1")
            patch_response = await client.patch(
                "/api/reviews/1/status",
                json={"processing_status": "on_hold"},
            )
            bulk_response = await client.post(
                "/api/reviews/bulk-status",
                json={"review_ids": [1, 2], "processing_status": "ignored"},
            )
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["recommendation_id"] == "1001"
    assert detail_response.status_code == 200
    assert detail_response.json()["review_text"] == "这是一条差评，需要处理"
    assert patch_response.status_code == 200
    assert patch_response.json()["updated_count"] == 1
    assert bulk_response.status_code == 200
    assert bulk_response.json()["updated_count"] == 2
