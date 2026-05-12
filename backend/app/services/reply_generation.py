from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.error_utils import format_exception_message
from app.models import ReplyDraft, ReplyStrategy, SteamGame, SteamReview
from app.services.aliyun_client import AliyunChatClient, AliyunChatOptions
from app.services.reply_skill import resolve_reply_skill_content


class ReplyAIClient(Protocol):
    async def generate_reply(self, prompt: str, options: AliyunChatOptions) -> str: ...


class ReplyGenerationError(RuntimeError):
    def __init__(self, message: str, draft_id: int | None = None) -> None:
        super().__init__(message)
        self.draft_id = draft_id


@dataclass(frozen=True)
class ReplyGenerationResult:
    draft: ReplyDraft


class ReplyGenerationService:
    def __init__(
        self,
        session: AsyncSession,
        ai_client_factory: Callable[[], ReplyAIClient] | None = None,
    ) -> None:
        self.session = session
        self.ai_client_factory = ai_client_factory or AliyunChatClient

    async def generate_for_review(self, review_id: int) -> ReplyGenerationResult:
        review = await self.session.get(SteamReview, review_id)
        if review is None:
            raise ReplyGenerationError("Review not found")
        game = await self.session.get(SteamGame, review.app_id)
        if game is None or game.game_scope != "owned":
            raise ReplyGenerationError("Competitor games do not support reply operations")

        strategy = await self._get_active_strategy()
        if strategy is None:
            raise ReplyGenerationError("Active reply strategy not found")

        prompt = build_reply_prompt(review, strategy)
        model_name = strategy.model_name
        options = AliyunChatOptions(model=model_name, temperature=strategy.temperature)

        try:
            content = await self.ai_client_factory().generate_reply(prompt, options)
        except Exception as exc:
            draft = await self._record_failed_draft(review, strategy, prompt, model_name, exc)
            raise ReplyGenerationError(format_exception_message(exc), draft.id) from exc

        draft = ReplyDraft(
            review_id=review.id,
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            content=content,
            status="pending_review",
            model_name=model_name,
            prompt_snapshot=prompt,
        )
        review.reply_status = "drafted"
        self.session.add(draft)
        await self.session.commit()
        await self.session.refresh(draft)
        return ReplyGenerationResult(draft=draft)

    async def _get_active_strategy(self) -> ReplyStrategy | None:
        strategy = await ensure_active_reply_strategy(self.session)
        return strategy

    async def _record_failed_draft(
        self,
        review: SteamReview,
        strategy: ReplyStrategy,
        prompt: str,
        model_name: str,
        exc: Exception,
    ) -> ReplyDraft:
        message = format_exception_message(exc)
        draft = ReplyDraft(
            review_id=review.id,
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            content="",
            status="generation_failed",
            model_name=model_name,
            prompt_snapshot=prompt,
            error_message=message,
        )
        review.reply_status = "generation_failed"
        self.session.add(draft)
        await self.session.commit()
        await self.session.refresh(draft)
        return draft


async def ensure_active_reply_strategy(session: AsyncSession) -> ReplyStrategy | None:
    result = await session.execute(
        select(ReplyStrategy)
        .where(ReplyStrategy.is_active.is_(True))
        .order_by(desc(ReplyStrategy.updated_at), desc(ReplyStrategy.id))
        .limit(1)
    )
    strategy = result.scalar_one_or_none()
    if strategy is not None:
        return strategy

    latest_result = await session.execute(
        select(ReplyStrategy)
        .order_by(desc(ReplyStrategy.updated_at), desc(ReplyStrategy.id))
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    if latest is not None:
        latest.is_active = True
        await session.commit()
        await session.refresh(latest)
        return latest

    settings = get_settings()
    default_skill = resolve_reply_skill_content(None)
    strategy = ReplyStrategy(
        name="默认回复 Skill",
        description="系统自动创建的默认 Steam 评论回复 Skill。",
        skill_content=default_skill,
        prompt_template=default_skill,
        model_name=settings.aliyun_model,
        temperature=0.4,
        is_active=True,
    )
    session.add(strategy)
    await session.commit()
    await session.refresh(strategy)
    return strategy


def build_reply_prompt(review: SteamReview, strategy: ReplyStrategy) -> str:
    skill_content = resolve_reply_skill_content(strategy.skill_content)
    context = {
        "app_id": review.app_id,
        "review_text": review.review_text or "",
        "sentiment": "好评" if review.voted_up else "差评",
        "playtime_forever": review.playtime_forever,
        "playtime_at_review": review.playtime_at_review,
        "votes_up": review.votes_up,
        "votes_funny": review.votes_funny,
        "comment_count": review.comment_count,
        "persona_name": review.persona_name or "",
        "steam_id": review.steam_id or "",
        "recommendation_id": review.recommendation_id,
    }
    return "\n\n".join(
        [
            "请基于下面的 Steam 评论回复 skill 文档，生成一条中文开发者回复草稿。",
            "你必须严格遵守 skill 中的角色、原则、判断流程、场景口径和输出要求。",
            f"策略名称：{strategy.name}",
            f"策略版本：v{strategy.version}",
            "Steam 评论 AI 回复 Skill 文档：\n" + skill_content,
            "评论信息：\n" + json.dumps(context, ensure_ascii=False, indent=2),
            "\n".join(
                [
                    "输出要求：",
                    "1. 先在心里完成判断和场景匹配。",
                    "2. 如果根据 skill 判断应该不回，只输出：",
                    "【判断：不回】",
                    "原因：...",
                    "3. 如果应该回复，只输出最终可发布的中文回复正文。",
                    "4. 不要输出标题、解释、Markdown 或 JSON。",
                ]
            ),
        ]
    )
