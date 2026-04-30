from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import RequireAdmin, hash_password
from app.models import User
from app.schemas import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[UserResponse])
async def list_users(
    session: SessionDependency,
    current_user: RequireAdmin,
    limit: int = Query(default=100, gt=0, le=500),
) -> list[User]:
    result = await session.execute(
        select(User).order_by(desc(User.created_at), desc(User.id)).limit(limit)
    )
    return list(result.scalars().all())


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    request: UserCreate,
    session: SessionDependency,
    current_user: RequireAdmin,
) -> User:
    result = await session.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        display_name=request.display_name,
        role=request.role,
        is_active=request.is_active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    request: UserUpdate,
    session: SessionDependency,
    current_user: RequireAdmin,
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if request.password is not None:
        user.password_hash = hash_password(request.password)
    if request.display_name is not None:
        user.display_name = request.display_name
    if request.role is not None:
        user.role = request.role
    if request.is_active is not None:
        user.is_active = request.is_active
    await session.commit()
    await session.refresh(user)
    return user
