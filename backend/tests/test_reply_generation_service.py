from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.main import app
from app.models import Base, ReplyDraft, ReplyStrategy, SteamGame, SteamReview
from app.services.aliyun_client import AliyunChatOptions
from app.services.reply_generation import ReplyGenerationError, ReplyGenerationService


class FakeAIClient:
    async def generate_reply(self, prompt: str, options: AliyunChatOptions) -> str:
        assert "这是一条需要认真回复的差评" in prompt
        assert options.model == "qwen-plus"
        return "感谢你的反馈，我们会继续优化相关体验。"


class FailingAIClient:
    async def generate_reply(self, prompt: str, options: AliyunChatOptions) -> str:
        raise RuntimeError("mock aliyun failure")


async def test_reply_generation_creates_pending_review_draft() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review = await seed_reply_generation_data(session)
        service = ReplyGenerationService(session, ai_client_factory=FakeAIClient)

        result = await service.generate_for_review(review.id)

        stored_review = await session.get(SteamReview, review.id)

    await engine.dispose()

    assert result.draft.content == "感谢你的反馈，我们会继续优化相关体验。"
    assert result.draft.status == "pending_review"
    assert result.draft.strategy_version == 1
    assert result.draft.model_name == "qwen-plus"
    assert result.draft.prompt_snapshot is not None
    assert "策略版本：v1" in result.draft.prompt_snapshot
    assert stored_review is not None
    assert stored_review.reply_status == "drafted"


async def test_reply_generation_records_failure_draft() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review = await seed_reply_generation_data(session)
        service = ReplyGenerationService(session, ai_client_factory=FailingAIClient)

        with pytest.raises(ReplyGenerationError) as exc_info:
            await service.generate_for_review(review.id)

        draft = await session.scalar(select(ReplyDraft).where(ReplyDraft.review_id == review.id))
        stored_review = await session.get(SteamReview, review.id)

    await engine.dispose()

    assert exc_info.value.draft_id is not None
    assert draft is not None
    assert draft.status == "generation_failed"
    assert draft.error_message == "mock aliyun failure"
    assert stored_review is not None
    assert stored_review.reply_status == "generation_failed"


async def test_get_reply_draft_route() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        review = await seed_reply_generation_data(seed_session)
        draft = ReplyDraft(
            review_id=review.id,
            strategy_id=1,
            strategy_version=1,
            content="草稿内容",
            status="pending_review",
            model_name="qwen-plus",
            prompt_snapshot="prompt",
        )
        seed_session.add(draft)
        await seed_session.commit()
        draft_id = draft.id

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/reply-drafts/{draft_id}")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    assert response.json()["content"] == "草稿内容"
    assert response.json()["status"] == "pending_review"


async def seed_reply_generation_data(session: AsyncSession) -> SteamReview:
    session.add(SteamGame(app_id=3350200, name="test game"))
    strategy = ReplyStrategy(
        id=1,
        name="默认策略",
        description="测试策略",
        prompt_template="请真诚、具体地回复用户。评论：{review_text}",
        reply_rules="不要争辩，不要承诺具体日期。",
        forbidden_terms=["亲亲"],
        good_examples=[
            {
                "title": "差评安抚",
                "review": "剧情不好",
                "reply": "感谢指出问题，我们会继续优化叙事体验。",
            }
        ],
        brand_voice="真诚、克制、负责。",
        classification_strategy="差评优先解释和安抚。",
        model_name="qwen-plus",
        temperature=0.3,
        is_active=True,
    )
    review = SteamReview(
        app_id=3350200,
        recommendation_id="1001",
        steam_id="steam-a",
        persona_name="玩家A",
        review_text="这是一条需要认真回复的差评",
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
    )
    session.add_all([strategy, review])
    await session.commit()
    await session.refresh(review)
    return review
