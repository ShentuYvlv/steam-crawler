from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TaskLog


async def add_task_log(
    session: AsyncSession,
    task_id: int,
    message: str,
    *,
    level: str = "info",
    details: dict | None = None,
) -> TaskLog:
    task_log = TaskLog(
        task_id=task_id,
        level=level,
        message=message,
        details=details,
    )
    session.add(task_log)
    await session.flush()
    return task_log
