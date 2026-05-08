import json

import httpx

from app.services.aliyun_client import (
    AliyunChatClient,
    AliyunChatOptions,
    normalize_aliyun_endpoint,
)


async def test_aliyun_client_uses_dashscope_generation_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == (
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        )
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "qwen-plus"
        assert payload["input"]["messages"][0]["role"] == "system"
        assert payload["input"]["messages"][1]["content"] == "hello"
        assert payload["parameters"]["result_format"] == "message"
        assert payload["parameters"]["temperature"] == 0.4
        return httpx.Response(
            200,
            json={
                "output": {
                    "choices": [
                        {"message": {"role": "assistant", "content": "reply content"}}
                    ]
                }
            },
        )

    client = AliyunChatClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    result = await client.generate_reply(
        "hello",
        AliyunChatOptions(model="qwen-plus", temperature=0.4),
    )

    assert result == "reply content"


async def test_aliyun_client_falls_back_to_compatible_endpoint() -> None:
    seen_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url).endswith("/services/aigc/text-generation/generation"):
            return httpx.Response(
                400,
                json={
                    "code": "InvalidParameter",
                    "message": "url error, please check url！",
                },
            )
        assert str(request.url) == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["messages"][1]["content"] == "hello"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "fallback reply"}}
                ]
            },
        )

    client = AliyunChatClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    result = await client.generate_reply(
        "hello",
        AliyunChatOptions(model="qwen-plus", temperature=0.4),
    )

    assert result == "fallback reply"
    assert len(seen_urls) == 2


def test_normalize_aliyun_endpoint() -> None:
    assert (
        normalize_aliyun_endpoint("https://dashscope.aliyuncs.com/api/v1")
        == "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    )
    assert (
        normalize_aliyun_endpoint("https://dashscope-intl.aliyuncs.com/api")
        == "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    )
    assert (
        normalize_aliyun_endpoint(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        )
        == "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    )
