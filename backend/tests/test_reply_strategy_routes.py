from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.main import app
from app.models import Base


async def test_reply_strategy_create_update_activate() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            create_response = await client.post(
                "/api/reply-strategies",
                json={
                    "name": "默认策略",
                    "description": "测试策略",
                    "skill_content": "# 回复 Skill\\n\\n先共情，再解释。",
                    "model_name": "qwen-plus",
                    "temperature": 0.4,
                    "is_active": True,
                },
            )
            active_response = await client.get("/api/reply-strategies/active")
            default_skill_response = await client.get("/api/reply-strategies/default-skill")
            update_response = await client.patch(
                "/api/reply-strategies/1",
                json={"skill_content": "# 更新后的 Skill\\n\\n先感谢，再说明后续计划。"},
            )
            second_response = await client.post(
                "/api/reply-strategies",
                json={
                    "name": "备用策略",
                    "skill_content": "# 备用 Skill\\n\\n给出更简短的回复。",
                    "is_active": False,
                },
            )
            activate_response = await client.post("/api/reply-strategies/2/activate")
            list_response = await client.get("/api/reply-strategies")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert create_response.status_code == 201
    assert create_response.json()["is_active"] is True
    assert create_response.json()["skill_content"].startswith("# 回复 Skill")
    assert active_response.status_code == 200
    assert active_response.json()["name"] == "默认策略"
    assert default_skill_response.status_code == 200
    assert "Steam 评论 AI 回复 Skill" in default_skill_response.json()["content"]
    assert update_response.status_code == 200
    assert update_response.json()["version"] == 2
    assert "更新后的 Skill" in update_response.json()["skill_content"]
    assert second_response.status_code == 201
    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True
    strategies = list_response.json()
    assert len(strategies) == 2
    assert sum(1 for strategy in strategies if strategy["is_active"]) == 1


async def test_get_active_reply_strategy_bootstraps_default() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/reply-strategies/active")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert response.json()["name"] == "默认回复 Skill"
