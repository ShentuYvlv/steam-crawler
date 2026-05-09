from __future__ import annotations

import asyncio
import random
import time
import warnings
from typing import TYPE_CHECKING, Any

import httpx

try:
    import orjson
except ImportError:
    orjson = None

from src.config import Config, get_config
from src.utils.oxylabs_proxy import (
    ProxyMode,
    build_proxy_log_fields,
    load_oxylabs_proxy_settings,
)
from src.utils.task_control import TaskCancelledError

if TYPE_CHECKING:
    import requests


class AsyncHttpClient:
    """Async HTTP client with retries, rate limiting, and optional proxy routing."""

    def __init__(
        self,
        config: Config | None = None,
        *,
        stop_event: Any | None = None,
        rate_limiter: Any | None = None,
        proxy_mode: ProxyMode = "none",
        sticky_session_port: int | None = None,
    ) -> None:
        self.config = config or get_config()
        self.stop_event = stop_event
        self.rate_limiter = rate_limiter
        self.proxy_mode = proxy_mode
        self._sticky_session_port = sticky_session_port
        self._direct_client: httpx.AsyncClient | None = None
        self._sticky_proxy_client: httpx.AsyncClient | None = None
        self._last_request_metadata = build_proxy_log_fields(self.proxy_mode)

    async def _get_direct_client(self) -> httpx.AsyncClient:
        if self._direct_client is None:
            self._direct_client = self._create_client()
        return self._direct_client

    async def _get_sticky_proxy_client(self) -> httpx.AsyncClient:
        if self._sticky_proxy_client is None:
            settings = load_oxylabs_proxy_settings()
            if self._sticky_session_port is None:
                self._sticky_session_port = settings.choose_sticky_session_port()
            proxy_url = settings.build_sticky_proxy_url(session_port=self._sticky_session_port)
            self._sticky_proxy_client = self._create_client(proxy=proxy_url)
        return self._sticky_proxy_client

    def _create_client(self, *, proxy: str | None = None) -> httpx.AsyncClient:
        limits = httpx.Limits(
            max_connections=self.config.http.max_connections,
            max_keepalive_connections=self.config.http.max_keepalive_connections,
        )
        return httpx.AsyncClient(
            headers={"User-Agent": self.config.http.user_agent},
            timeout=httpx.Timeout(self.config.http.timeout),
            limits=limits,
            verify=False,
            proxy=proxy,
        )

    async def _send_with_direct_client(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        client = await self._get_direct_client()
        return await client.get(url, params=params)

    async def _send_with_rotating_proxy(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        proxy_url: str,
    ) -> httpx.Response:
        async with self._create_client(proxy=proxy_url) as client:
            return await client.get(url, params=params)

    async def _send_with_sticky_proxy(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        client = await self._get_sticky_proxy_client()
        return await client.get(url, params=params)

    async def _send_request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        settings = load_oxylabs_proxy_settings()
        if not settings.is_active_for_mode(self.proxy_mode):
            self._last_request_metadata = build_proxy_log_fields(
                self.proxy_mode,
                settings=settings,
            )
            return await self._send_with_direct_client(url, params=params)

        if self.proxy_mode == "rotate_per_request":
            proxy_url = settings.build_rotating_proxy_url()
            metadata = build_proxy_log_fields(
                self.proxy_mode,
                settings=settings,
                session_port=None,
            )
            try:
                response = await self._send_with_rotating_proxy(
                    url,
                    params=params,
                    proxy_url=proxy_url,
                )
                self._last_request_metadata = metadata
                return response
            except httpx.RequestError as proxy_exc:
                if not settings.direct_fallback:
                    self._last_request_metadata = build_proxy_log_fields(
                        self.proxy_mode,
                        settings=settings,
                        proxy_error=proxy_exc,
                    )
                    raise
                self._last_request_metadata = build_proxy_log_fields(
                    self.proxy_mode,
                    settings=settings,
                    fallback_used=True,
                    proxy_error=proxy_exc,
                )
                return await self._send_with_direct_client(url, params=params)

        if self._sticky_session_port is None:
            self._sticky_session_port = settings.choose_sticky_session_port()
        metadata = build_proxy_log_fields(
            self.proxy_mode,
            settings=settings,
            session_port=self._sticky_session_port,
        )
        try:
            response = await self._send_with_sticky_proxy(url, params=params)
            self._last_request_metadata = metadata
            return response
        except httpx.RequestError as proxy_exc:
            if not settings.direct_fallback:
                self._last_request_metadata = build_proxy_log_fields(
                    self.proxy_mode,
                    settings=settings,
                    session_port=self._sticky_session_port,
                    proxy_error=proxy_exc,
                )
                raise
            self._last_request_metadata = build_proxy_log_fields(
                self.proxy_mode,
                settings=settings,
                session_port=self._sticky_session_port,
                fallback_used=True,
                proxy_error=proxy_exc,
            )
            return await self._send_with_direct_client(url, params=params)

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        delay: bool = True,
    ) -> httpx.Response:
        last_exception: Exception | None = None

        for attempt in range(self.config.http.max_retries + 1):
            try:
                self._raise_if_cancelled()
                if self.rate_limiter is not None:
                    await self.rate_limiter.before_request(self.stop_event)

                response = await self._send_request(url, params=params)
                response.raise_for_status()

                if self.rate_limiter is not None:
                    await self.rate_limiter.record_success()
                if delay and self.rate_limiter is None:
                    await self._delay()
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exception = exc
                if self.rate_limiter is not None:
                    await self.rate_limiter.record_error(exc)
                if attempt < self.config.http.max_retries:
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    print(
                        f"请求失败，{wait_time:.1f} 秒后重试 "
                        f"({attempt + 1}/{self.config.http.max_retries}): {exc}"
                    )
                    await self._sleep(wait_time)

        raise last_exception  # type: ignore[misc]

    async def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        delay: bool = True,
    ) -> dict[str, Any]:
        response = await self.get(url, params=params, delay=delay)
        if orjson is not None:
            try:
                return orjson.loads(response.content)
            except Exception:
                pass
        return response.json()

    def get_last_request_metadata(self) -> dict[str, Any]:
        return dict(self._last_request_metadata)

    async def _delay(self) -> None:
        delay = random.uniform(
            self.config.http.min_delay,
            self.config.http.max_delay,
        )
        await self._sleep(delay)

    async def _sleep(self, delay: float) -> None:
        remaining = delay
        while remaining > 0:
            self._raise_if_cancelled()
            chunk = min(0.5, remaining)
            await asyncio.sleep(chunk)
            remaining -= chunk

    def _raise_if_cancelled(self) -> None:
        if self.stop_event is not None and self.stop_event.is_set():
            raise TaskCancelledError()

    async def close(self) -> None:
        if self._sticky_proxy_client is not None:
            await self._sticky_proxy_client.aclose()
            self._sticky_proxy_client = None
        if self._direct_client is not None:
            await self._direct_client.aclose()
            self._direct_client = None


class HttpClient:
    """Legacy sync HTTP client kept for backward compatibility."""

    def __init__(self, config: Config | None = None) -> None:
        warnings.warn(
            "HttpClient 已废弃，请使用 AsyncHttpClient 替代。",
            DeprecationWarning,
            stacklevel=2,
        )
        self.config = config or get_config()
        import requests
        import urllib3

        self._requests = requests
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.http.user_agent})
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        delay: bool = True,
    ) -> requests.Response:
        last_exception: Exception | None = None

        for attempt in range(self.config.http.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config.http.timeout,
                    verify=False,
                )
                response.raise_for_status()
                if delay:
                    self._delay()
                return response
            except self._requests.RequestException as exc:
                last_exception = exc
                if attempt < self.config.http.max_retries:
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    print(
                        f"请求失败，{wait_time:.1f} 秒后重试 "
                        f"({attempt + 1}/{self.config.http.max_retries}): {exc}"
                    )
                    time.sleep(wait_time)

        raise last_exception  # type: ignore[misc]

    def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        delay: bool = True,
    ) -> dict[str, Any]:
        response = self.get(url, params=params, delay=delay)
        return response.json()

    def _delay(self) -> None:
        delay = random.uniform(
            self.config.http.min_delay,
            self.config.http.max_delay,
        )
        time.sleep(delay)
