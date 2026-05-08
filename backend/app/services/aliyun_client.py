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
    compatible_endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.aliyun_api_key
        self.timeout = timeout
        self.endpoint = normalize_aliyun_endpoint(settings.aliyun_base_url)
        self.transport = transport

    async def generate_reply(self, prompt: str, options: AliyunChatOptions) -> str:
        if not self.api_key:
            raise AliyunClientError("ALIYUN_API_KEY is not configured")

        primary_payload: dict[str, Any] = {
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
            primary_payload["parameters"]["temperature"] = options.temperature

        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await self._post(client, self.endpoint, primary_payload)

            if should_fallback_to_compatible(response):
                response = await self._post(
                    client,
                    self.compatible_endpoint,
                    build_compatible_payload(prompt, options),
                )

        if response.status_code >= 400:
            detail = _extract_error_message(response)
            raise AliyunClientError(
                f"Aliyun API failed: HTTP {response.status_code} {detail}"
            )

        data = response.json()
        try:
            content = extract_response_content(data)
        except (KeyError, IndexError, TypeError) as exc:
            raise AliyunClientError(
                "Aliyun API response missing message content"
            ) from exc

        content = str(content).strip()
        if not content:
            raise AliyunClientError("Aliyun API returned empty reply content")
        return content

    async def _post(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        return await client.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )


def _extract_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text
    if isinstance(data, dict):
        return str(data.get("message") or data.get("code") or response.text)
    return response.text


def extract_response_content(data: dict[str, Any]) -> str:
    if "output" in data:
        return data["output"]["choices"][0]["message"]["content"]
    return data["choices"][0]["message"]["content"]


def normalize_aliyun_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/services/aigc/text-generation/generation"):
        return normalized
    if normalized.endswith("/compatible-mode/v1/chat/completions"):
        return normalized
    if normalized.endswith("/api/v1"):
        return normalized + "/services/aigc/text-generation/generation"
    if normalized.endswith("/api"):
        return normalized + "/v1/services/aigc/text-generation/generation"
    if normalized.endswith("/v1"):
        return normalized + "/services/aigc/text-generation/generation"
    return normalized + "/api/v1/services/aigc/text-generation/generation"


def build_compatible_payload(prompt: str, options: AliyunChatOptions) -> dict[str, Any]:
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
    return payload


def should_fallback_to_compatible(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    try:
        data = response.json()
    except ValueError:
        return False
    if not isinstance(data, dict):
        return False
    message = str(data.get("message") or "")
    code = str(data.get("code") or "")
    return code == "InvalidParameter" and "url error" in message.lower()
