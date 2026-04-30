from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.security import hash_password
from app.main import app
from app.models import Base, User


async def test_login_and_admin_user_management() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add(
            User(
                username="admin",
                password_hash=hash_password("password123"),
                role="admin",
                is_active=True,
            )
        )
        await seed_session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login_response = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "password123"},
            )
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            me_response = await client.get("/api/auth/me", headers=headers)
            create_response = await client.post(
                "/api/users",
                headers=headers,
                json={
                    "username": "operator",
                    "password": "password123",
                    "role": "operator",
                    "is_active": True,
                },
            )
            list_response = await client.get("/api/users", headers=headers)
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert login_response.status_code == 200
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "admin"
    assert create_response.status_code == 201
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2
