from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import ReplyStrategy
from app.schemas import ReplyStrategyCreate, ReplyStrategyResponse, ReplyStrategyUpdate

router = APIRouter(prefix="/reply-strategies", tags=["reply-strategies"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[ReplyStrategyResponse])
async def list_reply_strategies(session: SessionDependency) -> list[ReplyStrategy]:
    result = await session.execute(
        select(ReplyStrategy).order_by(
            desc(ReplyStrategy.is_active),
            desc(ReplyStrategy.updated_at),
        )
    )
    return list(result.scalars().all())


@router.get("/active", response_model=ReplyStrategyResponse)
async def get_active_reply_strategy(session: SessionDependency) -> ReplyStrategy:
    result = await session.execute(select(ReplyStrategy).where(ReplyStrategy.is_active.is_(True)))
    strategy = result.scalars().first()
    if strategy is None:
        raise HTTPException(status_code=404, detail="Active reply strategy not found")
    return strategy


@router.post("", response_model=ReplyStrategyResponse, status_code=201)
async def create_reply_strategy(
    request: ReplyStrategyCreate,
    session: SessionDependency,
) -> ReplyStrategy:
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
    return strategy


@router.patch("/{strategy_id}", response_model=ReplyStrategyResponse)
async def update_reply_strategy(
    strategy_id: int,
    request: ReplyStrategyUpdate,
    session: SessionDependency,
) -> ReplyStrategy:
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
    return strategy


@router.post("/{strategy_id}/activate", response_model=ReplyStrategyResponse)
async def activate_reply_strategy(
    strategy_id: int,
    session: SessionDependency,
) -> ReplyStrategy:
    strategy = await session.get(ReplyStrategy, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Reply strategy not found")

    await deactivate_all_strategies(session, except_strategy_id=strategy.id)
    strategy.is_active = True
    await session.commit()
    await session.refresh(strategy)
    return strategy


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
    return {
        "name": request.name,
        "description": request.description,
        "prompt_template": request.prompt_template,
        "reply_rules": request.reply_rules,
        "forbidden_terms": request.forbidden_terms,
        "good_examples": [example.model_dump() for example in request.good_examples],
        "brand_voice": request.brand_voice,
        "classification_strategy": request.classification_strategy,
        "model_name": request.model_name,
        "temperature": request.temperature,
        "is_active": request.is_active,
    }


def strategy_update_values(request: ReplyStrategyUpdate) -> dict[str, Any]:
    values = request.model_dump(exclude_unset=True, exclude={"is_active"})
    if "good_examples" in values and values["good_examples"] is not None:
        values["good_examples"] = [example.model_dump() for example in request.good_examples or []]
    return values
