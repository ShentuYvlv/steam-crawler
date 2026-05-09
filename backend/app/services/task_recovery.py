from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import SyncJob, TaskSchedule
from app.schemas import ReviewSyncRequest
from app.services.developer_replies import recover_pending_reply_sends


async def recover_incomplete_steam_jobs() -> None:
    from app.api.routes.tasks import _run_review_sync_job

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SyncJob)
            .where(
                SyncJob.job_type == "steam_review_sync",
                SyncJob.status.in_(("pending", "waiting", "running")),
                SyncJob.app_id.is_not(None),
            )
            .order_by(SyncJob.created_at, SyncJob.id)
        )
        jobs = list(result.scalars().all())

        for job in jobs:
            schedule = (
                await session.get(TaskSchedule, job.schedule_id) if job.schedule_id else None
            )
            options = schedule.options if schedule is not None and schedule.options else {}
            request = ReviewSyncRequest(
                app_id=job.app_id,
                schedule_id=job.schedule_id,
                limit=job.requested_limit,
                language=str(options.get("language") or "schinese"),
                filter=str(options.get("filter") or "recent"),
                review_type=str(options.get("review_type") or "all"),
                purchase_type=str(options.get("purchase_type") or "all"),
                use_review_quality=bool(options.get("use_review_quality", True)),
                per_page=int(options.get("per_page") or 100),
            )
            asyncio.create_task(_run_review_sync_job(job.id, request))

    await recover_pending_reply_sends()
