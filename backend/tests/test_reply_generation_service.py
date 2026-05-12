from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, ReplyDraft, ReplyStrategy, SteamGame, SteamReview, User
from app.services.aliyun_client import AliyunChatOptions
from app.services.reply_generation import ReplyGenerationError, ReplyGenerationService


class FakeAIClient:
    async def generate_reply(self, prompt: str, options: AliyunChatOptions) -> str:
        assert "这是一条需要认真回复的差评" in prompt
        assert "Steam 评论 AI 回复 Skill" in prompt
        assert options.model
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
    assert "Steam 评论 AI 回复 Skill 文档" in result.draft.prompt_snapshot
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


async def test_reply_generation_auto_bootstraps_active_strategy() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(SteamGame(app_id=3350200, name="test game", game_scope="owned"))
        review = SteamReview(
            app_id=3350200,
            recommendation_id="1002",
            steam_id="steam-b",
            persona_name="玩家B",
            review_text="这是一条需要认真回复的差评",
            voted_up=False,
            votes_up=2,
            votes_funny=0,
            comment_count=0,
            playtime_forever=1.0,
            timestamp_created=datetime(2026, 4, 28, 12, tzinfo=UTC),
            sync_type="stock",
            source_type="csv",
            processing_status="pending",
            reply_status="none",
        )
        session.add(review)
        await session.commit()
        await session.refresh(review)

        service = ReplyGenerationService(session, ai_client_factory=FakeAIClient)
        result = await service.generate_for_review(review.id)
        strategy = await session.scalar(
            select(ReplyStrategy).where(ReplyStrategy.is_active.is_(True))
        )

    await engine.dispose()

    assert result.draft.strategy_id is not None
    assert strategy is not None
    assert strategy.name == "默认回复 Skill"
    assert strategy.is_active is True


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


async def test_update_reply_draft_can_reject_draft() -> None:
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
        admin = User(
            username="admin",
            password_hash=hash_password("password123"),
            role="admin",
            is_active=True,
        )
        seed_session.add_all([draft, admin])
        await seed_session.commit()
        draft_id = draft.id
        review_id = review.id
        token = create_access_token(admin)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/reply-drafts/{draft_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"status": "rejected"},
            )
    finally:
        app.dependency_overrides.clear()

    async with session_factory() as check_session:
        stored_draft = await check_session.get(ReplyDraft, draft_id)
        stored_review = await check_session.get(SteamReview, review_id)

    await engine.dispose()

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert stored_draft is not None
    assert stored_draft.reviewed_at is not None
    assert stored_review is not None
    assert stored_review.reply_status == "rejected"


async def test_reply_draft_routes_reject_competitor_games() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add(SteamGame(app_id=4000000, name="competitor game", game_scope="competitor"))
        review = SteamReview(
            app_id=4000000,
            recommendation_id="c-1001",
            steam_id="steam-c",
            persona_name="玩家C",
            review_text="竞品评论",
            voted_up=False,
            votes_up=1,
            votes_funny=0,
            comment_count=0,
            playtime_forever=1.0,
            timestamp_created=datetime(2026, 4, 28, 12, tzinfo=UTC),
            sync_type="stock",
            source_type="csv",
            processing_status="pending",
            reply_status="drafted",
        )
        draft = ReplyDraft(
            review=review,
            content="竞品草稿",
            status="pending_review",
            model_name="qwen-plus",
        )
        admin = User(
            username="admin",
            password_hash=hash_password("password123"),
            role="admin",
            is_active=True,
        )
        seed_session.add_all([review, draft, admin])
        await seed_session.commit()
        draft_id = draft.id
        token = create_access_token(admin)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            get_response = await client.get(f"/api/reply-drafts/{draft_id}")
            patch_response = await client.patch(
                f"/api/reply-drafts/{draft_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"status": "rejected"},
            )
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert get_response.status_code == 403
    assert patch_response.status_code == 403


async def seed_reply_generation_data(session: AsyncSession) -> SteamReview:
    session.add(SteamGame(app_id=3350200, name="test game", game_scope="owned"))
    strategy = ReplyStrategy(
        id=1,
        name="默认策略",
        description="测试策略",
        skill_content="# 自定义回复 Skill\n\n请先共情，再给出克制回复。",
        prompt_template="请真诚、具体地回复用户。评论：{review_text}",
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


async def test_reply_generation_rejects_competitor_game() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(SteamGame(app_id=4000000, name="competitor game", game_scope="competitor"))
        strategy = ReplyStrategy(
            id=1,
            name="默认策略",
            description="测试策略",
            skill_content="# 自定义回复 Skill",
            prompt_template="请回复",
            model_name="qwen-plus",
            temperature=0.3,
            is_active=True,
        )
        review = SteamReview(
            app_id=4000000,
            recommendation_id="c-1001",
            steam_id="steam-c",
            persona_name="玩家C",
            review_text="竞品评论",
            voted_up=False,
            votes_up=1,
            votes_funny=0,
            comment_count=0,
            playtime_forever=1.0,
            timestamp_created=datetime(2026, 4, 28, 12, tzinfo=UTC),
            sync_type="stock",
            source_type="csv",
            processing_status="pending",
            reply_status="none",
        )
        session.add_all([strategy, review])
        await session.commit()
        await session.refresh(review)

        service = ReplyGenerationService(session, ai_client_factory=FakeAIClient)
        with pytest.raises(ReplyGenerationError, match="Competitor games do not support reply operations"):
            await service.generate_for_review(review.id)

    await engine.dispose()
