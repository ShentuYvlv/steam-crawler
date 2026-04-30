from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReplyDraft, ReplyStrategy, SteamReview
from app.services.aliyun_client import AliyunChatClient, AliyunChatOptions


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
            raise ReplyGenerationError(str(exc), draft.id) from exc

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
        result = await self.session.execute(
            select(ReplyStrategy)
            .where(ReplyStrategy.is_active.is_(True))
            .order_by(desc(ReplyStrategy.updated_at), desc(ReplyStrategy.id))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _record_failed_draft(
        self,
        review: SteamReview,
        strategy: ReplyStrategy,
        prompt: str,
        model_name: str,
        exc: Exception,
    ) -> ReplyDraft:
        draft = ReplyDraft(
            review_id=review.id,
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            content="",
            status="generation_failed",
            model_name=model_name,
            prompt_snapshot=prompt,
            error_message=str(exc),
        )
        review.reply_status = "generation_failed"
        self.session.add(draft)
        await self.session.commit()
        await self.session.refresh(draft)
        return draft


def build_reply_prompt(review: SteamReview, strategy: ReplyStrategy) -> str:
    context = {
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
        "brand_voice": strategy.brand_voice or "",
        "reply_rules": strategy.reply_rules or "",
        "forbidden_terms": "、".join(strategy.forbidden_terms or []),
        "classification_strategy": strategy.classification_strategy or "",
        "good_examples": _format_good_examples(strategy.good_examples or []),
    }
    strategy_prompt = _safe_format(strategy.prompt_template, context)
    return "\n\n".join(
        [
            "请基于下面的策略和 Steam 用户评论，生成一条中文开发者回复草稿。",
            f"策略名称：{strategy.name}",
            f"策略版本：v{strategy.version}",
            f"策略模板：\n{strategy_prompt}",
            f"品牌语气：\n{context['brand_voice'] or '未配置'}",
            f"回复规则：\n{context['reply_rules'] or '未配置'}",
            f"禁止用语：{context['forbidden_terms'] or '未配置'}",
            f"分类/处理策略：\n{context['classification_strategy'] or '未配置'}",
            f"优秀示例：\n{context['good_examples'] or '未配置'}",
            "评论信息：\n" + json.dumps(context, ensure_ascii=False, indent=2),
            "输出要求：只输出最终回复正文；不要输出标题、解释、Markdown 或 JSON。",
        ]
    )


def _format_good_examples(examples: list[dict]) -> str:
    lines: list[str] = []
    for index, example in enumerate(examples, start=1):
        lines.append(
            "\n".join(
                [
                    f"{index}. {example.get('title') or '示例'}",
                    f"用户评论：{example.get('review') or ''}",
                    f"开发者回复：{example.get('reply') or ''}",
                ]
            )
        )
    return "\n\n".join(lines)


def _safe_format(template: str, values: dict[str, object]) -> str:
    try:
        return template.format_map(_SafeFormatDict(values))
    except (KeyError, ValueError):
        return template


class _SafeFormatDict(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
