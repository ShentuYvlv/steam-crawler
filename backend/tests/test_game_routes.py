from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, SteamGame, SteamReview, SyncJob, TaskSchedule, User


async def test_games_route_returns_all_games_with_schedule_and_latest_task() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add_all(
            [
                SteamGame(app_id=3350200, name="情感反诈模拟器", game_scope="owned"),
                SteamGame(app_id=4000000, name="备用游戏", game_scope="competitor"),
                SteamGame(app_id=5000000, name="零评论游戏", game_scope="competitor"),
            ]
        )
        schedule = TaskSchedule(
            name="情感反诈模拟器",
            task_type="steam_review_sync",
            is_enabled=True,
            app_id=3350200,
            interval="daily",
            hour=9,
            minute=0,
            options={"language": "schinese"},
        )
        seed_session.add(schedule)
        await seed_session.flush()
        seed_session.add_all(
            [
                SteamReview(
                    app_id=3350200,
                    recommendation_id="a-1",
                    review_text="评论1",
                    sync_type="stock",
                    source_type="csv",
                ),
                SteamReview(
                    app_id=3350200,
                    recommendation_id="a-2",
                    review_text="评论2",
                    sync_type="stock",
                    source_type="csv",
                ),
                SteamReview(
                    app_id=4000000,
                    recommendation_id="b-1",
                    review_text="评论3",
                    sync_type="stock",
                    source_type="csv",
                ),
            ]
        )
        seed_session.add(
            SyncJob(
                schedule_id=schedule.id,
                schedule_name=schedule.name,
                trigger_type="scheduled",
                app_id=3350200,
                job_type="steam_review_sync",
                source_type="steam_api",
                status="success",
                inserted_count=2,
                updated_count=0,
                skipped_count=0,
            )
        )
        await seed_session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/games")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["name"] == "备用游戏"
    game = next(item for item in payload if item["app_id"] == 3350200)
    assert game["game_scope"] == "owned"
    assert game["review_count"] == 2
    assert game["has_schedule"] is True
    assert game["schedule_enabled"] is True
    assert game["latest_task_status"] == "success"
    zero_review_game = next(item for item in payload if item["app_id"] == 5000000)
    assert zero_review_game["review_count"] == 0


async def test_game_mutation_routes_and_sync_actions(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        seed_session.add(SteamGame(app_id=3350200, name="情感反诈模拟器", game_scope="owned"))
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

    monkeypatch.setattr("app.api.routes.games._run_review_sync_job", noop_run_review_sync_job)

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}
            create_response = await client.post(
                "/api/games",
                headers=headers,
                json={
                    "app_id": 4000000,
                    "name": "新增游戏",
                    "game_scope": "competitor",
                    "sync": {
                        "enabled": True,
                        "hour": 13,
                        "language": "schinese",
                        "filter": "recent",
                        "review_type": "all",
                        "purchase_type": "all",
                        "use_review_quality": True,
                        "per_page": 100,
                    },
                },
            )
            update_response = await client.patch(
                "/api/games/3350200",
                headers=headers,
                json={
                    "name": "情感反诈模拟器-新版",
                    "game_scope": "owned",
                    "sync": {
                        "enabled": False,
                        "hour": 15,
                        "language": "english",
                        "filter": "updated",
                        "review_type": "negative",
                        "purchase_type": "steam",
                        "use_review_quality": False,
                        "per_page": 50,
                    },
                },
            )
            sync_one_response = await client.post("/api/games/3350200/sync", headers=headers)
            sync_all_response = await client.post("/api/games/sync-all", headers=headers)
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert create_response.status_code == 201
    assert create_response.json()["game_scope"] == "competitor"
    assert create_response.json()["schedule_enabled"] is True
    assert create_response.json()["schedule_hour"] == 13
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "情感反诈模拟器-新版"
    assert update_response.json()["game_scope"] == "owned"
    assert update_response.json()["schedule_enabled"] is False
    assert update_response.json()["schedule_options"]["language"] == "english"
    assert sync_one_response.status_code == 202
    assert sync_one_response.json()["accepted_count"] == 1
    assert sync_all_response.status_code == 202
    assert sync_all_response.json()["accepted_count"] == 2
