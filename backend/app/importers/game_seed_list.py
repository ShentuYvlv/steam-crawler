from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SteamGame

DEFAULT_GAME_SEED_LIST: tuple[tuple[str, int], ...] = (
    ("隐形守护者", 998940),
    ("完蛋！我被美女包围了！", 3282390),
    ("美女请别影响我学习", 2786680),
    ("美女请别影响我修仙", 3545990),
    ("飞越 13 号房", 2095300),
    ("盛世天下", 3478050),
    ("你好！我们还有场恋爱没有谈", 3167180),
    ("江山北望", 3831120),
    ("名利游戏", 2758000),
    ("失恋玩家", 4005300),
    ("代号三国龙起", 3412900),
    ("底特律变人", 1222140),
    ("双人成行", 1426210),
    ("碟影成双", 2757350),
    ("逃出升天", 1222700),
)


@dataclass(frozen=True)
class ImportGameSeedListResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


async def import_game_seed_list(
    session: AsyncSession,
    seed_list: tuple[tuple[str, int], ...] = DEFAULT_GAME_SEED_LIST,
) -> ImportGameSeedListResult:
    inserted = 0
    updated = 0
    skipped = 0

    for name, app_id in seed_list:
        game = await session.get(SteamGame, app_id)
        if game is None:
            session.add(SteamGame(app_id=app_id, name=name))
            await session.flush()
            inserted += 1
            continue
        if game.name != name:
            game.name = name
            updated += 1
            continue
        skipped += 1

    await session.commit()
    return ImportGameSeedListResult(inserted=inserted, updated=updated, skipped=skipped)
