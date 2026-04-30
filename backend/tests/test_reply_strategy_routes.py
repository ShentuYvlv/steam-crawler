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
                    "prompt_template": "请基于评论生成回复：{review_text}",
                    "reply_rules": "先共情，再解释。",
                    "forbidden_terms": ["攻击用户"],
                    "good_examples": [
                        {
                            "title": "差评安抚",
                            "review": "不好玩",
                            "reply": "感谢反馈，我们会继续优化。",
                        }
                    ],
                    "brand_voice": "真诚、克制、友好",
                    "classification_strategy": "优先处理高赞差评",
                    "model_name": "qwen-plus",
                    "temperature": 0.4,
                    "is_active": True,
                },
            )
            active_response = await client.get("/api/reply-strategies/active")
            update_response = await client.patch(
                "/api/reply-strategies/1",
                json={"reply_rules": "先感谢，再说明后续计划。"},
            )
            second_response = await client.post(
                "/api/reply-strategies",
                json={
                    "name": "备用策略",
                    "prompt_template": "备用模板：{review_text}",
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
    assert active_response.status_code == 200
    assert active_response.json()["name"] == "默认策略"
    assert update_response.status_code == 200
    assert update_response.json()["version"] == 2
    assert second_response.status_code == 201
    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True
    strategies = list_response.json()
    assert len(strategies) == 2
    assert sum(1 for strategy in strategies if strategy["is_active"]) == 1
