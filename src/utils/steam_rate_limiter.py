from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

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
        self.probe_interval_seconds = 600.0

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

    async def record_success(self) -> None:
        async with self._lock:
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
    ) -> dict[str, Any]:
        while True:
            if stop_event is not None and stop_event.is_set():
                raise TaskCancelledError()
            probe_result = await self.probe()
            if on_probe is not None:
                await on_probe(probe_result)
            if probe_result["ok"]:
                return probe_result
            await _sleep_with_cancel(self.probe_interval_seconds, stop_event)

    async def probe(self) -> dict[str, Any]:
        now = time.monotonic()
        async with httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                )
            },
            timeout=httpx.Timeout(20.0),
            verify=False,
        ) as client:
            try:
                response = await client.get(
                    "https://store.steampowered.com/ajaxappreviews/10",
                    params={
                        "json": "1",
                        "cursor": "*",
                        "language": "all",
                        "filter": "recent",
                        "review_type": "all",
                        "purchase_type": "all",
                        "num_per_page": "1",
                    },
                )
                response.raise_for_status()
                await self.record_success()
                async with self._lock:
                    self._last_probe_at = now
                    self._last_probe_error = None
                    self._cooldown_until = 0.0
                    return {"ok": True, "probe": "steam_ajaxappreviews", **self._snapshot_locked(now)}
            except Exception as exc:
                snapshot = await self.record_error(exc)
                async with self._lock:
                    self._last_probe_at = now
                    self._last_probe_error = str(exc) or type(exc).__name__
                return {
                    "ok": False,
                    "probe": "steam_ajaxappreviews",
                    "error": str(exc) or type(exc).__name__,
                    "exception_type": type(exc).__name__,
                    "next_probe_seconds": self.probe_interval_seconds,
                    **snapshot,
                }

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
