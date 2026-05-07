from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.importers.game_seed_list import import_game_seed_list
from app.models import Base, SteamGame


async def test_import_game_seed_list_adds_and_updates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(SteamGame(app_id=998940, name="旧名字"))
        await session.commit()
        result = await import_game_seed_list(
            session,
            (
                ("隐形守护者", 998940),
                ("完蛋！我被美女包围了！", 3282390),
            ),
        )

    async with session_factory() as session:
        updated = await session.get(SteamGame, 998940)
        inserted = await session.get(SteamGame, 3282390)

    await engine.dispose()

    assert result.inserted == 1
    assert result.updated == 1
    assert updated is not None and updated.name == "隐形守护者"
    assert inserted is not None and inserted.name == "完蛋！我被美女包围了！"
