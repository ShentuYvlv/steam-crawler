from __future__ import annotations

import argparse
import asyncio

from app.core.database import AsyncSessionLocal
from app.importers import import_game_seed_list


def main() -> None:
    argparse.ArgumentParser(description="Import built-in Steam game seed list.").parse_args()
    asyncio.run(_run())


async def _run() -> None:
    async with AsyncSessionLocal() as session:
        result = await import_game_seed_list(session)
    print(
        "game seed import completed: "
        f"inserted={result.inserted}, "
        f"updated={result.updated}, "
        f"skipped={result.skipped}"
    )


if __name__ == "__main__":
    main()
