"""
Steam 开发者评论回复模块。

调用 Steam Community 的 setdeveloperresponse 接口，为用户评测设置开发者回复。
"""

from __future__ import annotations

import asyncio
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Optional

import httpx

from src.config import Config, get_config


def load_cookie_header(cookie_file: str | Path) -> str:
    """从文件读取 Cookie header。

    支持两种格式：
    - 文件内容就是完整 Cookie header
    - DevTools 抓包文本中单独一行 `cookie` 后跟 Cookie header
    """
    path = Path(cookie_file)
    text = path.read_text(encoding="utf-8").strip()
    lines = [line.strip() for line in text.splitlines()]

    for index, line in enumerate(lines):
        if line.lower() == "cookie":
            for candidate in lines[index + 1:]:
                if candidate:
                    return candidate

    if text.lower().startswith("cookie:"):
        return text.split(":", 1)[1].strip()

    return text


def extract_session_id(cookie_header: str) -> str:
    """从 Cookie header 提取 Steam sessionid。"""
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    if "sessionid" not in cookies:
        raise ValueError("Cookie 中缺少 sessionid")
    return cookies["sessionid"].value


class DeveloperReplyClient:
    """Steam Community 开发者回复客户端。"""

    def __init__(
        self,
        cookie_header: str,
        session_id: Optional[str] = None,
        config: Optional[Config] = None,
    ):
        self.config = config or get_config()
        self.cookie_header = cookie_header
        self.session_id = session_id or extract_session_id(cookie_header)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "User-Agent": self.config.http.user_agent,
                "Cookie": self.cookie_header,
                "Origin": "https://steamcommunity.com",
                "Referer": "https://steamcommunity.com/",
                "X-Requested-With": "XMLHttpRequest",
            }
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(self.config.http.timeout),
                verify=False,
            )
        return self._client

    async def set_developer_response(
        self,
        recommendation_id: str,
        response_text: str,
    ) -> dict[str, Any]:
        """为单条评测设置开发者回复。"""
        client = await self._get_client()
        url = (
            "https://steamcommunity.com/userreviews/setdeveloperresponse/"
            f"{recommendation_id}"
        )
        response = await client.post(
            url,
            data={
                "developer_response": response_text,
                "sessionid": self.session_id,
            },
        )
        response.raise_for_status()
        data = response.json()
        return {
            "recommendationid": recommendation_id,
            "success": data.get("success") == 1,
            "response": data,
        }

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


async def reply_to_reviews(
    client: DeveloperReplyClient,
    reviews: list[dict[str, Any]],
    response_text: str,
    limit: Optional[int] = None,
    delay_seconds: float = 0.5,
) -> list[dict[str, Any]]:
    """按顺序回复评测列表。"""
    results: list[dict[str, Any]] = []
    target_reviews = reviews[:limit] if limit is not None else reviews

    for review in target_reviews:
        recommendation_id = str(review.get("recommendationid", "")).strip()
        if not recommendation_id:
            continue

        try:
            result = await client.set_developer_response(
                recommendation_id=recommendation_id,
                response_text=response_text,
            )
        except Exception as exc:
            result = {
                "recommendationid": recommendation_id,
                "success": False,
                "error": str(exc),
            }

        results.append(result)
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    return results
