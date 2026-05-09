from __future__ import annotations

import asyncio
import copy
import random
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from src.config import get_config
from src.utils.http_client import AsyncHttpClient
from src.utils.steam_reviews_api import build_ajaxappreviews_params
from src.utils.task_control import SteamTemporarilyUnavailableError, TaskCancelledError

ProbeCallback = Callable[[dict[str, Any]], Awaitable[None]]


class SteamRateLimiter:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._recent_requests: deque[float] = deque()
        self._next_request_at = 0.0
        self._cooldown_until = 0.0
        self._failure_streak = 0
        self._consecutive_successes = 0
        self._last_probe_at = 0.0
        self._last_probe_error: str | None = None
        self.probe_interval_seconds = 60.0

    async def before_request(self, stop_event: Any | None = None) -> dict[str, Any]:
        while True:
            wait_time = 0.0
            async with self._lock:
                now = time.monotonic()
                self._prune_recent_requests(now)
                if self._cooldown_until > now:
                    wait_time = self._cooldown_until - now
                else:
                    spacing = self._current_spacing_seconds()
                    ready_at = max(self._next_request_at, now)
                    wait_time = max(0.0, ready_at - now)
                    if wait_time <= 0:
                        jitter = self._current_jitter_seconds()
                        self._next_request_at = now + spacing + jitter
                        self._recent_requests.append(now)
                        return self._snapshot_locked(now)
            await _sleep_with_cancel(wait_time, stop_event)

    async def record_success(self, *, reset_failures: bool = False) -> None:
        async with self._lock:
            if reset_failures:
                self._failure_streak = 0
                self._cooldown_until = 0.0
                self._consecutive_successes = 1
                return
            self._consecutive_successes += 1
            if self._consecutive_successes >= 3 and self._failure_streak > 0:
                self._failure_streak -= 1

    async def record_error(self, exc: Exception) -> dict[str, Any]:
        async with self._lock:
            now = time.monotonic()
            severe = self.is_availability_error(exc)
            self._consecutive_successes = 0
            if severe:
                self._failure_streak += 1
                cooldown_seconds = self._cooldown_seconds_for_streak(self._failure_streak)
                self._cooldown_until = max(self._cooldown_until, now + cooldown_seconds)
                self._last_probe_error = str(exc) or type(exc).__name__
            return self._snapshot_locked(now)

    async def wait_until_available(
        self,
        *,
        stop_event: Any | None = None,
        on_probe: ProbeCallback | None = None,
        app_id: int,
        language: str = "schinese",
        filter_type: str = "recent",
        review_type: str = "all",
        purchase_type: str = "all",
        use_review_quality: bool = True,
    ) -> dict[str, Any]:
        while True:
            if stop_event is not None and stop_event.is_set():
                raise TaskCancelledError()
            probe_result = await self.probe(
                app_id=app_id,
                language=language,
                filter_type=filter_type,
                review_type=review_type,
                purchase_type=purchase_type,
                use_review_quality=use_review_quality,
            )
            if on_probe is not None:
                await on_probe(probe_result)
            if probe_result["ok"]:
                return probe_result
            next_probe_seconds = float(probe_result.get("next_probe_seconds", self.probe_interval_seconds))
            await _sleep_with_cancel(next_probe_seconds, stop_event)

    async def probe(
        self,
        *,
        app_id: int,
        language: str,
        filter_type: str,
        review_type: str,
        purchase_type: str,
        use_review_quality: bool,
    ) -> dict[str, Any]:
        now = time.monotonic()
        config = copy.deepcopy(get_config())
        config.http.timeout = self._probe_timeout_seconds()
        client = AsyncHttpClient(config, proxy_mode="rotate_per_request")
        try:
            payload = await client.get_json(
                f"https://store.steampowered.com/ajaxappreviews/{app_id}",
                params=self._build_probe_params(
                    language=language,
                    filter_type=filter_type,
                    review_type=review_type,
                    purchase_type=purchase_type,
                    use_review_quality=use_review_quality,
                ),
                delay=False,
            )
            if payload.get("success") != 1:
                raise httpx.RemoteProtocolError(
                    f"Steam probe success flag invalid: {payload.get('success')}"
                )
            await self.record_success(reset_failures=True)
            async with self._lock:
                self._last_probe_at = now
                self._last_probe_error = None
                self._cooldown_until = 0.0
                return {
                    "ok": True,
                    "probe": "steam_ajaxappreviews",
                    "app_id": app_id,
                    "next_probe_seconds": self._next_probe_seconds_locked(now),
                    **self._snapshot_locked(now),
                    **client.get_last_request_metadata(),
                }
        except Exception as exc:
            snapshot = await self.record_error(exc)
            async with self._lock:
                self._last_probe_at = now
                self._last_probe_error = str(exc) or type(exc).__name__
                next_probe_seconds = self._next_probe_seconds_locked(now)
            return {
                "ok": False,
                "probe": "steam_ajaxappreviews",
                "app_id": app_id,
                "error": str(exc) or type(exc).__name__,
                "exception_type": type(exc).__name__,
                "next_probe_seconds": next_probe_seconds,
                **snapshot,
                **client.get_last_request_metadata(),
            }
        finally:
            await client.close()

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            now = time.monotonic()
            self._prune_recent_requests(now)
            return self._snapshot_locked(now)

    def _prune_recent_requests(self, now: float) -> None:
        cutoff = now - 120.0
        while self._recent_requests and self._recent_requests[0] < cutoff:
            self._recent_requests.popleft()

    def _current_mode(self, now: float) -> str:
        if self._cooldown_until > now:
            return "cooldown"
        request_volume = len(self._recent_requests)
        if self._failure_streak >= 2 or request_volume >= 24:
            return "protected"
        if request_volume >= 10:
            return "steady"
        return "fast"

    def _current_spacing_seconds(self) -> float:
        mode = self._current_mode(time.monotonic())
        if mode == "protected":
            return 2.5
        if mode == "steady":
            return 1.0
        return 0.2

    def _current_jitter_seconds(self) -> float:
        mode = self._current_mode(time.monotonic())
        if mode == "protected":
            return random.uniform(1.0, 2.0)
        if mode == "steady":
            return random.uniform(0.5, 1.25)
        return random.uniform(0.2, 0.6)

    def _cooldown_seconds_for_streak(self, failure_streak: int) -> float:
        if failure_streak >= 4:
            return 300.0
        if failure_streak == 3:
            return 180.0
        if failure_streak == 2:
            return 90.0
        return 30.0

    def is_availability_error(self, exc: Exception) -> bool:
        if isinstance(
            exc,
            (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.PoolTimeout,
                httpx.ReadTimeout,
                httpx.RemoteProtocolError,
            ),
        ):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {403, 429} or exc.response.status_code >= 500
        if isinstance(exc, SteamTemporarilyUnavailableError):
            return True
        return False

    def _probe_timeout_seconds(self) -> float:
        return max(20.0, float(get_config().http.timeout))

    def _build_probe_params(
        self,
        *,
        language: str,
        filter_type: str,
        review_type: str,
        purchase_type: str,
        use_review_quality: bool,
    ) -> dict[str, Any]:
        return build_ajaxappreviews_params(
            cursor="*",
            language=language,
            filter_type=filter_type,
            review_type=review_type,
            purchase_type=purchase_type,
            num_per_page=1,
            use_review_quality=use_review_quality,
        )

    def _next_probe_seconds_locked(self, now: float) -> float:
        cooldown_remaining = max(0.0, self._cooldown_until - now)
        if cooldown_remaining > 0:
            return max(30.0, min(300.0, round(cooldown_remaining, 2)))
        if self._failure_streak >= 4:
            return 300.0
        if self._failure_streak == 3:
            return 180.0
        if self._failure_streak == 2:
            return 90.0
        return 30.0

    def _snapshot_locked(self, now: float) -> dict[str, Any]:
        return {
            "mode": self._current_mode(now),
            "recent_request_count": len(self._recent_requests),
            "failure_streak": self._failure_streak,
            "consecutive_successes": self._consecutive_successes,
            "cooldown_remaining_seconds": max(0.0, round(self._cooldown_until - now, 2)),
            "probe_interval_seconds": self.probe_interval_seconds,
            "last_probe_error": self._last_probe_error,
        }


_steam_rate_limiter: SteamRateLimiter | None = None


def get_steam_rate_limiter() -> SteamRateLimiter:
    global _steam_rate_limiter
    if _steam_rate_limiter is None:
        _steam_rate_limiter = SteamRateLimiter()
    return _steam_rate_limiter


async def _sleep_with_cancel(wait_time: float, stop_event: Any | None = None) -> None:
    if wait_time <= 0:
        return
    remaining = wait_time
    while remaining > 0:
        if stop_event is not None and stop_event.is_set():
            raise TaskCancelledError()
        chunk = min(0.5, remaining)
        await asyncio.sleep(chunk)
        remaining -= chunk
