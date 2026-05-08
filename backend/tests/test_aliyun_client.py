import json

import httpx

from app.services.aliyun_client import AliyunChatClient, AliyunChatOptions


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
