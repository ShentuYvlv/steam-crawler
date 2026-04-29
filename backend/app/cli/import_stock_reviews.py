import argparse
import asyncio
from pathlib import Path

from app.core.database import AsyncSessionLocal
from app.importers import import_stock_reviews


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import stock Steam reviews from CSV.")
    parser.add_argument("--file", required=True, type=Path, help="CSV file path.")
    parser.add_argument(
        "--app-id",
        type=int,
        help="Fallback Steam app id when CSV URL lacks app id.",
    )
    parser.add_argument("--limit", type=int, help="Maximum rows to process.")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, do not write database.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if not args.file.exists():
        raise FileNotFoundError(f"CSV file not found: {args.file}")

    async with AsyncSessionLocal() as session:
        result = await import_stock_reviews(
            session,
            args.file,
            app_id=args.app_id,
            limit=args.limit,
            dry_run=args.dry_run,
        )

    mode = "dry-run" if args.dry_run else "import"
    print(
        f"{mode} completed: inserted={result.inserted}, "
        f"updated={result.updated}, skipped={result.skipped}"
    )


if __name__ == "__main__":
    asyncio.run(main())
