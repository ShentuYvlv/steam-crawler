from datetime import datetime

from pydantic import BaseModel, Field


class ReplyStrategyBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    skill_content: str = Field(min_length=1)
    model_name: str = "qwen-plus"
    temperature: float | None = Field(default=None, ge=0, le=2)


class ReplyStrategyCreate(ReplyStrategyBase):
    is_active: bool = False


class ReplyStrategyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    skill_content: str | None = Field(default=None, min_length=1)
    model_name: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    is_active: bool | None = None


class ReplyStrategyResponse(ReplyStrategyBase):
    id: int
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReplySkillTemplateResponse(BaseModel):
    content: str
