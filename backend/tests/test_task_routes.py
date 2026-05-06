from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, SyncJob, User


async def test_task_schedule_and_list_routes() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add(
            SyncJob(
                app_id=3350200,
                job_type="steam_review_sync",
                source_type="steam_api",
                status="success",
                inserted_count=1,
                updated_count=2,
                skipped_count=3,
            )
        )
        admin = User(
            username="admin",
            password_hash=hash_password("password123"),
            role="admin",
            is_active=True,
        )
        seed_session.add(admin)
        await seed_session.commit()
        token = create_access_token(admin)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}
            list_response = await client.get("/api/tasks")
            schedule_response = await client.patch(
                "/api/tasks/schedule",
                headers=headers,
                json={
                    "is_enabled": True,
                    "app_id": 3350200,
                    "interval": "daily",
                    "minute": 0,
                    "options": {"language": "schinese", "filter": "recent"},
                },
            )
            get_schedule_response = await client.get("/api/tasks/schedule")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert list_response.status_code == 200
    assert list_response.json()[0]["inserted_count"] == 1
    assert schedule_response.status_code == 200
    assert schedule_response.json()["is_enabled"] is True
    assert get_schedule_response.status_code == 200
    assert get_schedule_response.json()["app_id"] == 3350200
