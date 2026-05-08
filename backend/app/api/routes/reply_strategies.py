from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import ReplyStrategy
from app.schemas import (
    ReplySkillTemplateResponse,
    ReplyStrategyCreate,
    ReplyStrategyResponse,
    ReplyStrategyUpdate,
)
from app.services.reply_skill import load_default_reply_skill_content, resolve_reply_skill_content

router = APIRouter(prefix="/reply-strategies", tags=["reply-strategies"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[ReplyStrategyResponse])
async def list_reply_strategies(session: SessionDependency) -> list[ReplyStrategyResponse]:
    result = await session.execute(
        select(ReplyStrategy).order_by(
            desc(ReplyStrategy.is_active),
            desc(ReplyStrategy.updated_at),
        )
    )
    return [serialize_strategy(strategy) for strategy in result.scalars().all()]


@router.get("/active", response_model=ReplyStrategyResponse)
async def get_active_reply_strategy(session: SessionDependency) -> ReplyStrategyResponse:
    result = await session.execute(select(ReplyStrategy).where(ReplyStrategy.is_active.is_(True)))
    strategy = result.scalars().first()
    if strategy is None:
        raise HTTPException(status_code=404, detail="Active reply strategy not found")
    return serialize_strategy(strategy)


@router.get("/default-skill", response_model=ReplySkillTemplateResponse)
async def get_default_reply_skill() -> ReplySkillTemplateResponse:
    return ReplySkillTemplateResponse(content=load_default_reply_skill_content())


@router.post("", response_model=ReplyStrategyResponse, status_code=201)
async def create_reply_strategy(
    request: ReplyStrategyCreate,
    session: SessionDependency,
) -> ReplyStrategyResponse:
    if request.is_active:
        await deactivate_all_strategies(session)

    strategy = ReplyStrategy(**strategy_values(request))
    session.add(strategy)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Reply strategy name already exists") from exc

    await session.refresh(strategy)
    return serialize_strategy(strategy)


@router.patch("/{strategy_id}", response_model=ReplyStrategyResponse)
async def update_reply_strategy(
    strategy_id: int,
    request: ReplyStrategyUpdate,
    session: SessionDependency,
) -> ReplyStrategyResponse:
    strategy = await session.get(ReplyStrategy, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Reply strategy not found")

    values = strategy_update_values(request)
    if values:
        for key, value in values.items():
            setattr(strategy, key, value)
        strategy.version += 1

    if request.is_active is True:
        await deactivate_all_strategies(session, except_strategy_id=strategy.id)
        strategy.is_active = True
    elif request.is_active is False:
        strategy.is_active = False

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Reply strategy name already exists") from exc

    await session.refresh(strategy)
    return serialize_strategy(strategy)


@router.post("/{strategy_id}/activate", response_model=ReplyStrategyResponse)
async def activate_reply_strategy(
    strategy_id: int,
    session: SessionDependency,
) -> ReplyStrategyResponse:
    strategy = await session.get(ReplyStrategy, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Reply strategy not found")

    await deactivate_all_strategies(session, except_strategy_id=strategy.id)
    strategy.is_active = True
    await session.commit()
    await session.refresh(strategy)
    return serialize_strategy(strategy)


async def deactivate_all_strategies(
    session: AsyncSession,
    *,
    except_strategy_id: int | None = None,
) -> None:
    statement = update(ReplyStrategy).values(is_active=False)
    if except_strategy_id is not None:
        statement = statement.where(ReplyStrategy.id != except_strategy_id)
    await session.execute(statement)


def strategy_values(request: ReplyStrategyCreate) -> dict[str, Any]:
    skill_content = resolve_reply_skill_content(request.skill_content)
    return {
        "name": request.name,
        "description": request.description,
        "skill_content": skill_content,
        "prompt_template": skill_content,
        "model_name": request.model_name,
        "temperature": request.temperature,
        "is_active": request.is_active,
    }


def strategy_update_values(request: ReplyStrategyUpdate) -> dict[str, Any]:
    values = request.model_dump(exclude_unset=True, exclude={"is_active"})
    if "skill_content" in values and values["skill_content"] is not None:
        normalized_skill = resolve_reply_skill_content(values["skill_content"])
        values["skill_content"] = normalized_skill
        values["prompt_template"] = normalized_skill
    return values


def serialize_strategy(strategy: ReplyStrategy) -> ReplyStrategyResponse:
    return ReplyStrategyResponse(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        skill_content=resolve_reply_skill_content(strategy.skill_content),
        model_name=strategy.model_name,
        temperature=strategy.temperature,
        version=strategy.version,
        is_active=strategy.is_active,
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
    )
