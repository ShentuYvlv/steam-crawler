"""
真实评论爬虫模块。

从 Steam 商店 ajaxappreviews 接口抓取逐条用户评论。
"""

from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Optional

from src.config import Config, get_config
from src.utils.oxylabs_proxy import build_proxy_log_fields
from src.utils.steam_rate_limiter import get_steam_rate_limiter
from src.utils.steam_reviews_api import build_ajaxappreviews_params
from src.utils.task_control import TaskCancelledError
from src.utils.http_client import AsyncHttpClient

if TYPE_CHECKING:
    from src.utils.ui import UIManager


PageCallback = Callable[[dict[str, Any]], Awaitable[None]]


class CommentScraper:
    """Steam 用户评论爬虫。

    使用 Steam 商店页面加载评论时调用的 ajaxappreviews 接口。
    不依赖 Cookie、登录态或浏览器会话。
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        ui_manager: Optional["UIManager"] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        self.config = config or get_config()
        self.client = AsyncHttpClient(
            self.config,
            stop_event=stop_event,
            rate_limiter=get_steam_rate_limiter(),
            proxy_mode="rotate_per_request",
        )
        self.ui = ui_manager
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
        return build_ajaxappreviews_params(
            cursor=cursor,
            language=language,
            filter_type=filter_type,
            review_type=review_type,
            purchase_type=purchase_type,
            num_per_page=num_per_page,
            use_review_quality=use_review_quality,
        )

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
        on_page: Optional[PageCallback] = None,
        collect_reviews: bool = True,
    ) -> dict[str, Any]:
        """抓取单个游戏的逐条评论。"""
        url = f"https://store.steampowered.com/ajaxappreviews/{app_id}"
        cursor = "*"
        reviews: list[dict[str, Any]] = []
        query_summary: dict[str, Any] = {}
        seen_recommendation_ids: set[str] = set()
        reached_since_timestamp = False
        total_review_count = 0
        page_index = 0

        while True:
            if self.stop_event and self.stop_event.is_set():
                raise TaskCancelledError()

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
            page_batch: list[dict[str, Any]] = []
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
                if collect_reviews:
                    reviews.append(review)
                page_batch.append(review)
                added += 1
                total_review_count += 1

                if limit is not None and total_review_count >= limit:
                    break

            if page_batch and on_page is not None:
                page_index += 1
                await on_page(
                    {
                        "app_id": app_id,
                        "page_index": page_index,
                        "page_review_count": len(page_batch),
                        "total_review_count": total_review_count,
                        "query_summary": query_summary,
                        "reviews": page_batch,
                    }
                )

            if limit is not None and total_review_count >= limit:
                if collect_reviews:
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
            "review_count": total_review_count if not collect_reviews else len(reviews),
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

    def get_transport_diagnostics(self) -> dict[str, Any]:
        return self.client.get_last_request_metadata() or build_proxy_log_fields("rotate_per_request")
