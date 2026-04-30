from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import CurrentUser, authenticate_user, create_access_token
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, session: SessionDependency) -> LoginResponse:
    user = await authenticate_user(session, request.username, request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return LoginResponse(access_token=create_access_token(user), user=user)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> User:
    return current_user
