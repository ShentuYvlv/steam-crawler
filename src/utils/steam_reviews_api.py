from __future__ import annotations

from typing import Any


def build_ajaxappreviews_params(
    *,
    cursor: str,
    language: str,
    filter_type: str,
    review_type: str,
    purchase_type: str,
    num_per_page: int,
    use_review_quality: bool,
) -> dict[str, Any]:
    return {
        "date_range_type": "all",
        "day_range": "30",
        "start_date": "-1",
        "end_date": "-1",
        "cursor": cursor,
        "filter_offtopic_activity": "1",
        "playtime_filter_max": "0",
        "playtime_filter_min": "0",
        "playtime_type": "all",
        "purchase_type": purchase_type,
        "review_type": review_type,
        "use_review_quality": "1" if use_review_quality else "0",
        "language": language,
        "filter": filter_type,
        "num_per_page": str(num_per_page),
    }
