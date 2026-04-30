from datetime import datetime

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=255)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=255)
    display_name: str | None = Field(default=None, max_length=120)
    role: str = Field(default="operator", pattern="^(admin|operator|viewer)$")
    is_active: bool = True


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=255)
    display_name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, pattern="^(admin|operator|viewer)$")
    is_active: bool | None = None
