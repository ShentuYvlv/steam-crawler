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
    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.aliyun_api_key
        self.timeout = timeout
        self.endpoint = settings.aliyun_base_url
        self.transport = transport

    async def generate_reply(self, prompt: str, options: AliyunChatOptions) -> str:
        if not self.api_key:
            raise AliyunClientError("ALIYUN_API_KEY is not configured")

        payload: dict[str, Any] = {
            "model": options.model,
            "input": {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是游戏开发团队的中文社区运营助手，"
                            "只输出可直接发送给 Steam 用户的开发者回复。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ]
            },
            "parameters": {"result_format": "message"},
        }
        if options.temperature is not None:
            payload["parameters"]["temperature"] = options.temperature

        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code >= 400:
            detail = _extract_error_message(response)
            raise AliyunClientError(
                f"Aliyun API failed: HTTP {response.status_code} {detail}"
            )

        data = response.json()
        try:
            content = data["output"]["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AliyunClientError(
                "Aliyun API response missing output.choices[0].message.content"
            ) from exc

        content = str(content).strip()
        if not content:
            raise AliyunClientError("Aliyun API returned empty reply content")
        return content


def _extract_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text
    if isinstance(data, dict):
        return str(data.get("message") or data.get("code") or response.text)
    return response.text
