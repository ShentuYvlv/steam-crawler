from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


class AliyunClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class AliyunChatOptions:
    model: str
    temperature: float | None = None


class AliyunChatClient:
    endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    def __init__(self, api_key: str | None = None, timeout: float = 60.0) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.aliyun_api_key
        self.timeout = timeout

    async def generate_reply(self, prompt: str, options: AliyunChatOptions) -> str:
        if not self.api_key:
            raise AliyunClientError("ALIYUN_API_KEY is not configured")

        payload: dict[str, Any] = {
            "model": options.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是游戏开发团队的中文社区运营助手，"
                        "只输出可直接发送给 Steam 用户的开发者回复。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        if options.temperature is not None:
            payload["temperature"] = options.temperature

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code >= 400:
            raise AliyunClientError(
                f"Aliyun API failed: HTTP {response.status_code} {response.text}"
            )

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AliyunClientError(
                "Aliyun API response missing choices[0].message.content"
            ) from exc

        content = str(content).strip()
        if not content:
            raise AliyunClientError("Aliyun API returned empty reply content")
        return content
