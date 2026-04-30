from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.main import app
from app.models import Base, DeveloperReply, ReplyDraft, SteamGame, SteamReview
from app.services.developer_replies import DeveloperReplyError, DeveloperReplyService


class FakeSteamReplyClient:
    async def set_developer_response(self, recommendation_id: str, response_text: str) -> dict:
        assert recommendation_id == "1001"
        assert response_text == "感谢反馈，我们会继续优化。"
        return {"success": True, "response": {"success": 1}}

    async def close(self) -> None:
        return None


async def test_developer_reply_send_updates_record_review_and_draft() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FakeSteamReplyClient)

        record = await service.send_reply(review.id, confirmed=True, draft_id=draft.id)

        stored_review = await session.get(SteamReview, review.id)
        stored_draft = await session.get(ReplyDraft, draft.id)

    await engine.dispose()

    assert record.status == "sent"
    assert record.sent_at is not None
    assert stored_review is not None
    assert stored_review.reply_status == "replied"
    assert stored_review.developer_response == "感谢反馈，我们会继续优化。"
    assert stored_draft is not None
    assert stored_draft.status == "sent"


async def test_developer_reply_requires_confirmation() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FakeSteamReplyClient)

        with pytest.raises(DeveloperReplyError):
            await service.send_reply(review.id, confirmed=False, draft_id=draft.id)

    await engine.dispose()


async def test_reply_records_delete_request_route() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        review, _ = await seed_review_with_draft(seed_session)
        record = DeveloperReply(
            review_id=review.id,
            recommendation_id=review.recommendation_id,
            content="已发送回复",
            status="sent",
        )
        seed_session.add(record)
        await seed_session.commit()
        record_id = record.id

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            list_response = await client.get("/api/reply-records")
            delete_response = await client.post(
                f"/api/reply-records/{record_id}/delete-request",
                json={"confirmed": True, "reason": "测试删除请求"},
            )
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert list_response.status_code == 200
    assert list_response.json()[0]["content"] == "已发送回复"
    assert delete_response.status_code == 200
    assert delete_response.json()["delete_status"] == "requested"
    assert delete_response.json()["delete_request_reason"] == "测试删除请求"


async def seed_review_with_draft(session: AsyncSession) -> tuple[SteamReview, ReplyDraft]:
    session.add(SteamGame(app_id=3350200, name="test game"))
    review = SteamReview(
        app_id=3350200,
        recommendation_id="1001",
        steam_id="steam-a",
        review_text="测试评论",
        voted_up=False,
        votes_up=10,
        votes_funny=1,
        comment_count=0,
        timestamp_created=datetime(2026, 4, 28, 12, tzinfo=UTC),
        sync_type="stock",
        source_type="csv",
        processing_status="pending",
        reply_status="drafted",
    )
    session.add(review)
    await session.flush()
    draft = ReplyDraft(
        review_id=review.id,
        content="感谢反馈，我们会继续优化。",
        status="pending_review",
        model_name="qwen-plus",
    )
    session.add(draft)
    await session.commit()
    await session.refresh(review)
    await session.refresh(draft)
    return review, draft
