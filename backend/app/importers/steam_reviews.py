from datetime import UTC, datetime
from typing import Any


def steam_api_review_to_values(app_id: int, review: dict[str, Any]) -> dict[str, Any]:
    author = review.get("author") or {}
    recommendation_id = str(review.get("recommendationid") or "").strip()
    developer_response = clean_string(review.get("developer_response"))

    return {
        "app_id": app_id,
        "recommendation_id": recommendation_id,
        "steam_id": clean_string(author.get("steamid")),
        "persona_name": clean_string(author.get("personaname")),
        "profile_url": clean_string(author.get("profile_url")),
        "review_url": build_review_url(author.get("steamid"), app_id),
        "language": clean_string(review.get("language")),
        "review_text": clean_string(review.get("review")) or "",
        "voted_up": review.get("voted_up"),
        "votes_up": parse_int(review.get("votes_up"), default=0),
        "votes_funny": parse_int(review.get("votes_funny"), default=0),
        "weighted_vote_score": parse_float(review.get("weighted_vote_score")),
        "comment_count": parse_int(review.get("comment_count"), default=0),
        "steam_purchase": review.get("steam_purchase"),
        "received_for_free": review.get("received_for_free"),
        "refunded": review.get("refunded"),
        "written_during_early_access": review.get("written_during_early_access"),
        "playtime_forever": minutes_to_hours(author.get("playtime_forever")),
        "playtime_at_review": minutes_to_hours(author.get("playtime_at_review")),
        "playtime_last_two_weeks": minutes_to_hours(author.get("playtime_last_two_weeks")),
        "num_games_owned": parse_int(author.get("num_games_owned")),
        "num_reviews": parse_int(author.get("num_reviews")),
        "timestamp_created": parse_unix_timestamp(review.get("timestamp_created")),
        "timestamp_updated": parse_unix_timestamp(review.get("timestamp_updated")),
        "last_played": parse_unix_timestamp(author.get("last_played")),
        "sync_type": "incremental",
        "source_type": "steam_api",
        "processing_status": "pending",
        "reply_status": "replied" if developer_response else "none",
        "developer_response": developer_response,
        "developer_response_created_at": parse_unix_timestamp(
            review.get("developer_response_timestamp")
        ),
        "raw_payload": review,
    }


def clean_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def build_review_url(steam_id: Any, app_id: int) -> str | None:
    steam_id_value = clean_string(steam_id)
    if steam_id_value is None:
        return None
    return f"https://steamcommunity.com/profiles/{steam_id_value}/recommended/{app_id}"


def parse_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def minutes_to_hours(value: Any) -> float | None:
    minutes = parse_float(value)
    if minutes is None:
        return None
    return round(minutes / 60, 2)


def parse_unix_timestamp(value: Any) -> datetime | None:
    timestamp = parse_int(value)
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)
