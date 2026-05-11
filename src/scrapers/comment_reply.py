from __future__ import annotations

import asyncio
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import httpx

from src.config import Config, get_config
from src.utils.oxylabs_diagnostics import fetch_proxy_location
from src.utils.oxylabs_proxy import (
    build_proxy_log_fields,
    load_oxylabs_proxy_settings,
)
from src.utils.steam_reply_proxy import (
    build_explicit_proxy_log_fields,
    probe_proxy_location,
)


def load_cookie_header(cookie_file: str | Path) -> str:
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
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    if "sessionid" not in cookies:
        raise ValueError("Cookie 中缺少 sessionid")
    return cookies["sessionid"].value


class DeveloperReplyClient:
    """Steam Community developer reply client with optional explicit proxy support."""

    def __init__(
        self,
        cookie_header: str,
        session_id: str | None = None,
        config: Config | None = None,
        proxy_session_port: int | None = None,
        proxy_url: str | None = None,
        proxy_direct_fallback: bool = False,
    ) -> None:
        self.config = config or get_config()
        self.cookie_header = cookie_header
        self.session_id = session_id or extract_session_id(cookie_header)
        self._direct_client: httpx.AsyncClient | None = None
        self._proxy_clients: dict[str, httpx.AsyncClient] = {}
        self._explicit_proxy_client: httpx.AsyncClient | None = None
        self._proxy_session_port = proxy_session_port
        self._explicit_proxy_url = proxy_url.strip() if proxy_url and proxy_url.strip() else None
        self._proxy_direct_fallback = proxy_direct_fallback
        self._last_request_metadata = (
            build_explicit_proxy_log_fields(
                self._explicit_proxy_url,
                fallback_enabled=self._proxy_direct_fallback,
            )
            if self._explicit_proxy_url
            else build_proxy_log_fields("sticky_session")
        )
        self._proxy_location_cache: dict[str, Any] | None = None

    def _build_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.config.http.user_agent,
            "Cookie": self.cookie_header,
            "Origin": "https://steamcommunity.com",
            "Referer": "https://steamcommunity.com/",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _create_client(self, *, proxy: str | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self._build_headers(),
            timeout=httpx.Timeout(max(float(self.config.http.timeout), 60.0)),
            verify=False,
            proxy=proxy,
        )

    async def _get_direct_client(self) -> httpx.AsyncClient:
        if self._direct_client is None:
            self._direct_client = self._create_client()
        return self._direct_client

    async def _get_proxy_client(self, *, proxy_scheme: str) -> httpx.AsyncClient:
        client = self._proxy_clients.get(proxy_scheme)
        if client is None:
            settings = load_oxylabs_proxy_settings()
            if self._proxy_session_port is None:
                self._proxy_session_port = settings.choose_sticky_session_port()
            proxy_url = settings.build_sticky_proxy_url(
                session_port=self._proxy_session_port,
                scheme_override=proxy_scheme,
            )
            client = self._create_client(proxy=proxy_url)
            self._proxy_clients[proxy_scheme] = client
        return client

    async def _get_explicit_proxy_client(self) -> httpx.AsyncClient:
        if self._explicit_proxy_client is None:
            self._explicit_proxy_client = self._create_client(proxy=self._explicit_proxy_url)
        return self._explicit_proxy_client

    async def _post_with_optional_proxy(
        self,
        url: str,
        *,
        data: dict[str, Any],
    ) -> httpx.Response:
        if self._explicit_proxy_url:
            metadata = build_explicit_proxy_log_fields(
                self._explicit_proxy_url,
                fallback_enabled=self._proxy_direct_fallback,
            )
            try:
                client = await self._get_explicit_proxy_client()
                response = await client.post(url, data=data)
                self._last_request_metadata = metadata
                return response
            except httpx.RequestError as proxy_exc:
                if not self._proxy_direct_fallback:
                    self._last_request_metadata = build_explicit_proxy_log_fields(
                        self._explicit_proxy_url,
                        fallback_enabled=self._proxy_direct_fallback,
                        proxy_error=proxy_exc,
                    )
                    raise
                self._last_request_metadata = build_explicit_proxy_log_fields(
                    self._explicit_proxy_url,
                    fallback_enabled=self._proxy_direct_fallback,
                    fallback_used=True,
                    proxy_error=proxy_exc,
                )
                client = await self._get_direct_client()
                return await client.post(url, data=data)

        settings = load_oxylabs_proxy_settings()
        if not settings.is_active_for_mode("sticky_session"):
            self._last_request_metadata = build_proxy_log_fields(
                "sticky_session",
                settings=settings,
            )
            client = await self._get_direct_client()
            return await client.post(url, data=data)

        if self._proxy_session_port is None:
            self._proxy_session_port = settings.choose_sticky_session_port()
        metadata = build_proxy_log_fields(
            "sticky_session",
            settings=settings,
            session_port=self._proxy_session_port,
        )
        last_proxy_exception: httpx.RequestError | None = None
        for proxy_scheme, _proxy_url in settings.proxy_url_candidates(
            "sticky_session",
            session_port=self._proxy_session_port,
        ):
            metadata = build_proxy_log_fields(
                "sticky_session",
                settings=settings,
                session_port=self._proxy_session_port,
                proxy_scheme=proxy_scheme,
            )
            try:
                client = await self._get_proxy_client(proxy_scheme=proxy_scheme)
                response = await client.post(url, data=data)
                self._last_request_metadata = metadata
                return response
            except httpx.RequestError as proxy_exc:
                last_proxy_exception = proxy_exc
        if not settings.direct_fallback:
            self._last_request_metadata = build_proxy_log_fields(
                "sticky_session",
                settings=settings,
                session_port=self._proxy_session_port,
                proxy_error=last_proxy_exception,
            )
            raise last_proxy_exception  # type: ignore[misc]
        self._last_request_metadata = build_proxy_log_fields(
            "sticky_session",
            settings=settings,
            session_port=self._proxy_session_port,
            fallback_used=True,
            proxy_error=last_proxy_exception,
        )
        client = await self._get_direct_client()
        return await client.post(url, data=data)

    async def set_developer_response(
        self,
        recommendation_id: str,
        response_text: str,
    ) -> dict[str, Any]:
        url = (
            "https://steamcommunity.com/userreviews/setdeveloperresponse/"
            f"{recommendation_id}"
        )
        response = await self._post_with_optional_proxy(
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

    def get_last_request_metadata(self) -> dict[str, Any]:
        return dict(self._last_request_metadata)

    async def get_transport_diagnostics(self) -> dict[str, Any]:
        if self._proxy_location_cache is None:
            if self._explicit_proxy_url:
                proxy_client = await self._get_explicit_proxy_client()
                self._proxy_location_cache = await probe_proxy_location(
                    self._explicit_proxy_url,
                    fallback_enabled=self._proxy_direct_fallback,
                    existing_client=proxy_client,
                )
            else:
                settings = load_oxylabs_proxy_settings()
                if settings.is_active_for_mode("sticky_session"):
                    proxy_client = await self._get_proxy_client(
                        proxy_scheme=self.get_last_request_metadata().get("proxy_scheme") or settings.scheme
                    )
                    self._proxy_location_cache = await fetch_proxy_location(
                        "sticky_session",
                        session_port=self._proxy_session_port,
                        proxy_scheme=self.get_last_request_metadata().get("proxy_scheme") or settings.scheme,
                        existing_client=proxy_client,
                    )
                else:
                    self._proxy_location_cache = build_proxy_log_fields("sticky_session")
        return {
            **self._last_request_metadata,
            **self._proxy_location_cache,
        }

    @property
    def proxy_session_port(self) -> int | None:
        return self._proxy_session_port

    async def close(self) -> None:
        if self._explicit_proxy_client is not None:
            await self._explicit_proxy_client.aclose()
            self._explicit_proxy_client = None
        for client in self._proxy_clients.values():
            await client.aclose()
        self._proxy_clients.clear()
        if self._direct_client is not None:
            await self._direct_client.aclose()
            self._direct_client = None


async def reply_to_reviews(
    client: DeveloperReplyClient,
    reviews: list[dict[str, Any]],
    response_text: str,
    limit: int | None = None,
    delay_seconds: float = 0.5,
) -> list[dict[str, Any]]:
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
