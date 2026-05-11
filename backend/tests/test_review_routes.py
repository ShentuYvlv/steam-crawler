from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import app.api.routes.reviews as review_routes
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.main import app
from app.models import Base, ReplyDraft, SteamGame, SteamReview


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


async def test_bulk_generate_reply_worker_processes_all_review_ids(monkeypatch) -> None:
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
                    recommendation_id="2001",
                    steam_id="steam-a",
                    review_text="评论 A",
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
                    recommendation_id="2002",
                    steam_id="steam-b",
                    review_text="评论 B",
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

    class FakeReplyGenerationService:
        def __init__(self, session: AsyncSession) -> None:
            self.session = session

        async def generate_for_review(self, review_id: int):
            review = await self.session.get(SteamReview, review_id)
            draft = ReplyDraft(
                review_id=review_id,
                content=f"草稿 {review_id}",
                status="pending_review",
                model_name="test-model",
            )
            if review is not None:
                review.reply_status = "drafted"
            self.session.add(draft)
            await self.session.commit()
            await self.session.refresh(draft)
            return type("Result", (), {"draft": draft})()

    monkeypatch.setattr(review_routes, "ReplyGenerationService", FakeReplyGenerationService)
    monkeypatch.setattr(review_routes, "AsyncSessionLocal", session_factory)

    async with session_factory() as seed_session:
        task = await review_routes._create_background_task(
            seed_session,
            job_type="bulk_reply_generation",
            source_type="aliyun_api",
            review_ids=[1, 2],
        )

    await review_routes._generate_reply_drafts_in_background(task.id, [1, 2])

    async with session_factory() as check_session:
        drafts = (
            await check_session.execute(select(ReplyDraft).order_by(ReplyDraft.review_id))
        ).scalars().all()
        task = await check_session.get(review_routes.SyncJob, task.id)

    await engine.dispose()

    assert [draft.review_id for draft in drafts] == [1, 2]
    assert task is not None
    assert task.inserted_count == 2
