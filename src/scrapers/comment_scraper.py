"""
真实评论爬虫模块。

从 Steam 商店 ajaxappreviews 接口抓取逐条用户评论。
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from src.config import Config, get_config
from src.utils.http_client import AsyncHttpClient
from src.utils.ui import UIManager


class CommentScraper:
    """Steam 用户评论爬虫。

    使用 Steam 商店页面加载评论时调用的 ajaxappreviews 接口。
    不依赖 Cookie、登录态或浏览器会话。
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        ui_manager: Optional[UIManager] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        self.config = config or get_config()
        self.client = AsyncHttpClient(self.config)
        self.ui = ui_manager or UIManager()
        self.stop_event = stop_event

    def _build_params(
        self,
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

    async def scrape_app_comments(
        self,
        app_id: int,
        limit: Optional[int] = None,
        since_timestamp: Optional[int] = None,
        language: str = "schinese",
        filter_type: str = "recent",
        review_type: str = "all",
        purchase_type: str = "all",
        num_per_page: int = 100,
        use_review_quality: bool = True,
    ) -> dict[str, Any]:
        """抓取单个游戏的逐条评论。"""
        url = f"https://store.steampowered.com/ajaxappreviews/{app_id}"
        cursor = "*"
        reviews: list[dict[str, Any]] = []
        query_summary: dict[str, Any] = {}
        seen_recommendation_ids: set[str] = set()
        reached_since_timestamp = False

        while True:
            if self.stop_event and self.stop_event.is_set():
                break

            params = self._build_params(
                cursor=cursor,
                language=language,
                filter_type=filter_type,
                review_type=review_type,
                purchase_type=purchase_type,
                num_per_page=num_per_page,
                use_review_quality=use_review_quality,
            )
            data = await self.client.get_json(url, params=params)

            if data.get("success") != 1:
                raise RuntimeError(f"Steam comments API returned success={data.get('success')}")

            if data.get("query_summary"):
                query_summary = data["query_summary"]

            page_reviews = data.get("reviews", [])
            if not page_reviews:
                break

            added = 0
            for review in page_reviews:
                timestamp_created = self._parse_timestamp(review.get("timestamp_created"))
                if since_timestamp is not None and timestamp_created is not None:
                    if timestamp_created < since_timestamp:
                        reached_since_timestamp = True
                        break

                recommendation_id = str(review.get("recommendationid", ""))
                if recommendation_id and recommendation_id in seen_recommendation_ids:
                    continue

                if recommendation_id:
                    seen_recommendation_ids.add(recommendation_id)
                reviews.append(review)
                added += 1

                if limit is not None and len(reviews) >= limit:
                    break

            if limit is not None and len(reviews) >= limit:
                reviews = reviews[:limit]
                break

            if reached_since_timestamp:
                break

            next_cursor = data.get("cursor")
            if not next_cursor or next_cursor == cursor or added == 0:
                break

            cursor = next_cursor

        return {
            "app_id": app_id,
            "query_summary": query_summary,
            "review_count": len(reviews),
            "reviews": reviews,
        }

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    async def close(self) -> None:
        await self.client.close()
