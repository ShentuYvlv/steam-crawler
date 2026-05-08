from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Final

from app.models import SyncJob
from app.services.task_logs import add_task_log

RUNNING_STATUSES: Final[set[str]] = {"pending", "waiting", "running", "cancel_requested"}
CANCELLABLE_STATUSES: Final[set[str]] = {"pending", "waiting", "running", "cancel_requested"}
TERMINAL_STATUSES: Final[set[str]] = {"success", "partial_success", "failed", "cancelled"}

_registry_lock = threading.Lock()
_cancel_events: dict[int, threading.Event] = {}
_active_tasks: set[int] = set()
_steam_sync_lock: asyncio.Lock | None = None


def get_steam_sync_lock() -> asyncio.Lock:
    global _steam_sync_lock
    if _steam_sync_lock is None:
        _steam_sync_lock = asyncio.Lock()
    return _steam_sync_lock


def register_cancel_event(task_id: int) -> threading.Event:
    with _registry_lock:
        event = _cancel_events.get(task_id)
        if event is None:
            event = threading.Event()
            _cancel_events[task_id] = event
        return event


def unregister_cancel_event(task_id: int) -> None:
    with _registry_lock:
        _cancel_events.pop(task_id, None)


def register_active_task(task_id: int) -> None:
    with _registry_lock:
        _active_tasks.add(task_id)


def unregister_active_task(task_id: int) -> None:
    with _registry_lock:
        _active_tasks.discard(task_id)


def is_task_active(task_id: int) -> bool:
    with _registry_lock:
        return task_id in _active_tasks


def request_task_cancel(task_id: int) -> None:
    with _registry_lock:
        event = _cancel_events.get(task_id)
        if event is not None:
            event.set()


def is_task_cancellable(status: str) -> bool:
    return status in CANCELLABLE_STATUSES


def is_task_running(status: str) -> bool:
    return status in RUNNING_STATUSES


async def finalize_cancelled_task(
    session,
    task: SyncJob,
    *,
    message: str,
    details: dict | None = None,
) -> None:
    task.status = "cancelled"
    task.error_message = None
    task.finished_at = datetime.now()
    await add_task_log(session, task.id, message, level="info", details=details)
