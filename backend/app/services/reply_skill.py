from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_FALLBACK_REPLY_SKILL = """# 《情感反诈模拟器》Steam 评论 AI 回复 Skill

你是《情感反诈模拟器》制作组的官方 Steam 运营账号。
你代表一个真诚、有温度、有立场的小型游戏工作室发声。

核心原则：
- 哄，不是辩
- 不输入新信息源
- 不能被断章取义
- 新作相关一律不回

输出要求：
- 如果判断应该不回，只输出：
【判断：不回】
原因：...
- 如果判断应该回复，只输出可直接发布的中文回复正文
- 不要输出标题、解释、Markdown 或 JSON
"""


@lru_cache(maxsize=1)
def load_default_reply_skill_content() -> str:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs" / "steam_reply_skill.md"
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8").strip()
            if content:
                return content
    packaged_default = Path(__file__).with_name("reply_skill_default.md")
    if packaged_default.exists():
        content = packaged_default.read_text(encoding="utf-8").strip()
        if content:
            return content
    return _FALLBACK_REPLY_SKILL.strip()


def resolve_reply_skill_content(content: str | None) -> str:
    normalized = (content or "").strip()
    if normalized:
        return normalized
    return load_default_reply_skill_content()
