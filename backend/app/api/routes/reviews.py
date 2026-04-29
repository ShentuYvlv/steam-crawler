from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import SyncJob
from app.schemas import (
    ReviewSyncRequest,
    ReviewSyncResponse,
    SyncJobDetailResponse,
    SyncJobListItem,
)
from app.services.review_sync import ReviewSyncOptions, SteamReviewSyncService

router = APIRouter(prefix="/reviews", tags=["reviews"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post("/sync", response_model=ReviewSyncResponse)
async def sync_reviews(
    request: ReviewSyncRequest,
    session: SessionDependency,
) -> ReviewSyncResponse:
    service = SteamReviewSyncService(session)
    result = await service.sync_reviews(
        ReviewSyncOptions(
            app_id=request.app_id,
            limit=request.limit,
            language=request.language,
            filter=request.filter,
            review_type=request.review_type,
            purchase_type=request.purchase_type,
            use_review_quality=request.use_review_quality,
            per_page=request.per_page,
        )
    )
    return ReviewSyncResponse(
        sync_job_id=result.sync_job_id,
        app_id=result.app_id,
        inserted=result.inserted,
        updated=result.updated,
        skipped=result.skipped,
        status=result.status,
        query_summary=result.query_summary,
    )


@router.get("/sync-jobs", response_model=list[SyncJobListItem])
async def list_sync_jobs(
    session: SessionDependency,
    limit: int = Query(default=50, gt=0, le=200),
) -> list[SyncJob]:
    result = await session.execute(
        select(SyncJob).order_by(desc(SyncJob.created_at), desc(SyncJob.id)).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/sync-jobs/{sync_job_id}", response_model=SyncJobDetailResponse)
async def get_sync_job(
    sync_job_id: int,
    session: SessionDependency,
) -> SyncJob:
    sync_job = await session.get(SyncJob, sync_job_id)
    if sync_job is None:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return sync_job
