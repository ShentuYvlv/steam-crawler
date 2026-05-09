from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, SyncJob, TaskSchedule, User


async def test_task_schedule_routes_and_task_filtering(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        schedule = TaskSchedule(
            name="主游戏每日同步",
            task_type="steam_review_sync",
            is_enabled=True,
            app_id=3350200,
            interval="daily",
            hour=9,
            minute=0,
            options={"language": "schinese", "filter": "recent"},
        )
        seed_session.add(schedule)
        await seed_session.flush()
        seed_session.add_all(
            [
                SyncJob(
                    schedule_id=schedule.id,
                    schedule_name=schedule.name,
                    trigger_type="scheduled",
                    app_id=3350200,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="success",
                    inserted_count=1,
                    updated_count=2,
                    skipped_count=3,
                ),
                SyncJob(
                    schedule_id=None,
                    schedule_name=None,
                    trigger_type="manual",
                    app_id=4000000,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="success",
                    inserted_count=0,
                    updated_count=1,
                    skipped_count=0,
                ),
            ]
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

    async def noop_run_review_sync_job(sync_job_id: int, request) -> None:
        return None

    monkeypatch.setattr("app.api.routes.tasks._run_review_sync_job", noop_run_review_sync_job)

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}
            list_response = await client.get("/api/tasks")
            filtered_response = await client.get("/api/tasks?schedule_id=1")
            app_filtered_response = await client.get("/api/tasks?app_id=3350200")
            schedules_response = await client.get("/api/tasks/schedules")
            create_response = await client.post(
                "/api/tasks/schedules",
                headers=headers,
                json={
                    "name": "备用游戏每日同步",
                    "is_enabled": False,
                    "app_id": 4000000,
                    "interval": "daily",
                    "hour": 14,
                    "options": {"language": "schinese", "filter": "recent"},
                },
            )
            update_response = await client.patch(
                "/api/tasks/schedules/2",
                headers=headers,
                json={"is_enabled": True, "hour": 15},
            )
            enqueue_response = await client.post(
                "/api/tasks/reviews-sync",
                headers=headers,
                json={
                    "app_id": 3350200,
                    "schedule_id": 1,
                    "language": "schinese",
                    "filter": "recent",
                    "review_type": "all",
                    "purchase_type": "all",
                    "use_review_quality": True,
                    "per_page": 100,
                },
            )
            detail_response = await client.get("/api/tasks/1")
            delete_response = await client.delete("/api/tasks/schedules/2", headers=headers)
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert list_response.status_code == 200
    assert len(list_response.json()) == 2
    assert list_response.json()[0]["trigger_type"] == "manual"
    assert filtered_response.status_code == 200
    assert len(filtered_response.json()) == 1
    assert filtered_response.json()[0]["schedule_name"] == "主游戏每日同步"
    assert app_filtered_response.status_code == 200
    assert len(app_filtered_response.json()) == 1
    assert app_filtered_response.json()[0]["app_id"] == 3350200
    assert schedules_response.status_code == 200
    assert schedules_response.json()[0]["name"] == "主游戏每日同步"
    assert create_response.status_code == 201
    assert create_response.json()["hour"] == 14
    assert update_response.status_code == 200
    assert update_response.json()["hour"] == 15
    assert update_response.json()["is_enabled"] is True
    assert enqueue_response.status_code == 202
    assert enqueue_response.json()["schedule_id"] == 1
    assert enqueue_response.json()["schedule_name"] == "主游戏每日同步"
    assert enqueue_response.json()["trigger_type"] == "manual"
    assert detail_response.status_code == 200
    assert detail_response.json()["schedule_id"] == 1
    assert detail_response.json()["schedule_name"] == "主游戏每日同步"
    assert (
        detail_response.json()["game_name"] is None
        or isinstance(detail_response.json()["game_name"], str)
    )
    assert "logs" in detail_response.json()
    assert delete_response.status_code == 204


async def test_cancel_task_route_marks_pending_and_running_tasks(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        admin = User(
            username="admin",
            password_hash=hash_password("password123"),
            role="admin",
            is_active=True,
        )
        seed_session.add(admin)
        seed_session.add_all(
            [
                SyncJob(
                    app_id=3350200,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="pending",
                ),
                SyncJob(
                    app_id=4005300,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="running",
                ),
            ]
        )
        await seed_session.commit()
        token = create_access_token(admin)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}
            pending_response = await client.post("/api/tasks/1/cancel", headers=headers)
            running_response = await client.post("/api/tasks/2/cancel", headers=headers)
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert pending_response.status_code == 200
    assert pending_response.json()["status"] == "cancelled"
    assert pending_response.json()["can_cancel"] is False
    assert running_response.status_code == 200
    assert running_response.json()["status"] == "cancel_requested"
    assert running_response.json()["can_cancel"] is True


async def test_task_detail_settles_orphaned_cancel_requested_task() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add(
            SyncJob(
                job_type="bulk_reply_generation",
                source_type="aliyun_api",
                status="cancel_requested",
                requested_limit=1,
            )
        )
        await seed_session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/tasks/1")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["can_cancel"] is False


async def test_task_list_sorts_active_first_and_supports_status_group_filter() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    now = datetime.now(tz=UTC)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add_all(
            [
                SyncJob(
                    app_id=1001,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="success",
                    created_at=now - timedelta(minutes=30),
                    finished_at=now - timedelta(minutes=20),
                ),
                SyncJob(
                    app_id=1002,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="pending",
                    created_at=now - timedelta(minutes=10),
                ),
                SyncJob(
                    app_id=1003,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="waiting",
                    created_at=now - timedelta(minutes=9),
                ),
                SyncJob(
                    app_id=1004,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="running",
                    created_at=now - timedelta(minutes=8),
                    started_at=now - timedelta(minutes=7),
                ),
                SyncJob(
                    app_id=1005,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="cancelled",
                    created_at=now - timedelta(minutes=6),
                    finished_at=now - timedelta(minutes=5),
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
            all_response = await client.get("/api/tasks")
            active_response = await client.get("/api/tasks?status_group=active")
            terminal_response = await client.get("/api/tasks?status_group=terminal")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert all_response.status_code == 200
    assert [item["status"] for item in all_response.json()] == [
        "running",
        "waiting",
        "pending",
        "success",
        "cancelled",
    ]

    assert active_response.status_code == 200
    assert [item["status"] for item in active_response.json()] == [
        "running",
        "waiting",
        "pending",
    ]

    assert terminal_response.status_code == 200
    assert [item["status"] for item in terminal_response.json()] == [
        "success",
        "cancelled",
    ]
