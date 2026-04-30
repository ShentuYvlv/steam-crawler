from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TaskLog


async def add_task_log(
    session: AsyncSession,
    task_id: int,
    message: str,
    *,
    level: str = "info",
    details: dict[str, Any] | None = None,
    commit: bool = False,
) -> TaskLog:
    log = TaskLog(
        task_id=task_id,
        level=level,
        message=message,
        details=details,
    )
    session.add(log)
    await session.flush()
    if commit:
        await session.commit()
    return log
