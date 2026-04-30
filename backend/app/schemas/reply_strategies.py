from datetime import datetime

from pydantic import BaseModel, Field


class ReplyExample(BaseModel):
    title: str = ""
    review: str = ""
    reply: str = ""


class ReplyStrategyBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    prompt_template: str = Field(min_length=1)
    reply_rules: str | None = None
    forbidden_terms: list[str] = []
    good_examples: list[ReplyExample] = []
    brand_voice: str | None = None
    classification_strategy: str | None = None
    model_name: str = "qwen-plus"
    temperature: float | None = Field(default=None, ge=0, le=2)


class ReplyStrategyCreate(ReplyStrategyBase):
    is_active: bool = False


class ReplyStrategyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    prompt_template: str | None = Field(default=None, min_length=1)
    reply_rules: str | None = None
    forbidden_terms: list[str] | None = None
    good_examples: list[ReplyExample] | None = None
    brand_voice: str | None = None
    classification_strategy: str | None = None
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
