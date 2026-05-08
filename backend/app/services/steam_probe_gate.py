from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from src.utils.steam_rate_limiter import get_steam_rate_limiter
from src.utils.task_control import TaskCancelledError

from app.models import SyncJob
from app.services.task_logs import add_task_log


async def wait_for_steam_availability(
    session: AsyncSession,
    task: SyncJob,
    *,
    cancel_event,
) -> None:
    limiter = get_steam_rate_limiter()
    task.status = "waiting"
    await add_task_log(
        session,
        task.id,
        "等待 Steam 可用性探针",
        details=await limiter.snapshot(),
    )
    await session.commit()

    async def record_probe(result: dict) -> None:
        await session.refresh(task)
        if task.status in {"cancel_requested", "cancelled"} or cancel_event.is_set():
            raise TaskCancelledError()
        await add_task_log(
            session,
            task.id,
            "Steam 可用性探针结果",
            level="info" if result.get("ok") else "warning",
            details=result,
        )
        await session.commit()

    await limiter.wait_until_available(stop_event=cancel_event, on_probe=record_probe)
