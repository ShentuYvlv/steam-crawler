import csv
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SyncJob
from app.repositories import SteamReviewRepository

STEAM_RECOMMENDED_APP_RE = re.compile(r"/recommended/(?P<app_id>\d+)")
CHINA_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class ImportStockReviewsResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


def stock_review_row_to_values(row: dict[str, str], default_app_id: int | None = None) -> dict:
    app_id = default_app_id or extract_app_id(row.get("评论链接", ""))
    recommendation_id = clean_string(row.get("ID"))
    developer_response = clean_string(row.get("开发者回复"))

    return {
        "app_id": app_id,
        "recommendation_id": recommendation_id,
        "steam_id": clean_string(row.get("SteamID")),
        "profile_url": extract_profile_url(row.get("评论链接", "")),
        "review_url": clean_string(row.get("评论链接")),
        "language": clean_string(row.get("语言")),
        "review_text": clean_string(row.get("评论内容")) or "",
        "voted_up": parse_bool(row.get("正面评价")),
        "votes_up": parse_int(row.get("有用票数"), default=0),
        "votes_funny": parse_int(row.get("有趣票数"), default=0),
        "weighted_vote_score": parse_float(row.get("参考价值分")),
        "comment_count": parse_int(row.get("回复数"), default=0),
        "steam_purchase": parse_bool(row.get("Steam购买")),
        "received_for_free": parse_bool(row.get("免费获取")),
        "refunded": None,
        "written_during_early_access": parse_bool(row.get("抢先体验评论")),
        "playtime_forever": parse_float(row.get("总游戏时长")),
        "playtime_at_review": parse_float(row.get("评论时游戏时长")),
        "playtime_last_two_weeks": parse_float(row.get("两周游戏时长")),
        "num_games_owned": parse_int(row.get("拥有游戏数")),
        "num_reviews": parse_int(row.get("发表测评数量")),
        "timestamp_created": parse_datetime(row.get("创建时间")),
        "timestamp_updated": parse_datetime(row.get("更新时间")),
        "last_played": parse_datetime(row.get("最后游玩时间")),
        "sync_type": "stock",
        "source_type": "csv",
        "processing_status": "pending",
        "reply_status": "replied" if developer_response else "none",
        "developer_response": developer_response,
        "developer_response_created_at": parse_datetime(row.get("开发者回复时间")),
        "raw_payload": row,
    }


async def import_stock_reviews(
    session: AsyncSession,
    file_path: Path,
    *,
    app_id: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> ImportStockReviewsResult:
    repository = SteamReviewRepository(session)
    inserted = 0
    updated = 0
    skipped = 0
    processed = 0
    sync_job = SyncJob(
        app_id=app_id,
        job_type="stock_import",
        source_type="csv",
        status="running",
        requested_limit=limit,
        started_at=datetime.now(tz=CHINA_TZ),
    )

    if not dry_run:
        session.add(sync_job)
        await session.flush()

    try:
        async for values in iter_stock_review_values(file_path, app_id=app_id):
            if limit is not None and processed >= limit:
                break
            processed += 1

            if not values.get("app_id") or not values.get("recommendation_id"):
                skipped += 1
                continue

            if dry_run:
                inserted += 1
                continue

            result = await repository.upsert_review(values)
            inserted += result.inserted
            updated += result.updated
            skipped += result.skipped

        if not dry_run:
            sync_job.status = "success"
            sync_job.inserted_count = inserted
            sync_job.updated_count = updated
            sync_job.skipped_count = skipped
            sync_job.finished_at = datetime.now(tz=CHINA_TZ)
            await session.commit()
    except Exception as exc:
        if not dry_run:
            sync_job.status = "failed"
            sync_job.inserted_count = inserted
            sync_job.updated_count = updated
            sync_job.skipped_count = skipped
            sync_job.error_message = str(exc)
            sync_job.finished_at = datetime.now(tz=CHINA_TZ)
            await session.commit()
        raise

    return ImportStockReviewsResult(inserted=inserted, updated=updated, skipped=skipped)


async def iter_stock_review_values(
    file_path: Path,
    *,
    app_id: int | None = None,
) -> AsyncIterator[dict]:
    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            yield stock_review_row_to_values(row, default_app_id=app_id)


def clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def extract_app_id(review_url: str) -> int | None:
    match = STEAM_RECOMMENDED_APP_RE.search(review_url)
    if match is None:
        return None
    return int(match.group("app_id"))


def extract_profile_url(review_url: str) -> str | None:
    if "/recommended/" not in review_url:
        return clean_string(review_url)
    return review_url.split("/recommended/", maxsplit=1)[0]


def parse_bool(value: str | None) -> bool | None:
    normalized = clean_string(value)
    if normalized is None:
        return None
    return normalized.upper() in {"TRUE", "1", "YES", "Y", "是", "真"}


def parse_int(value: str | None, default: int | None = None) -> int | None:
    normalized = clean_string(value)
    if normalized is None:
        return default
    try:
        return int(float(normalized))
    except ValueError:
        return default


def parse_float(value: str | None) -> float | None:
    normalized = clean_string(value)
    if normalized is None:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def parse_datetime(value: str | None) -> datetime | None:
    normalized = clean_string(value)
    if normalized is None:
        return None

    for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(normalized, date_format)
            return parsed.replace(tzinfo=CHINA_TZ)
        except ValueError:
            continue
    return None
