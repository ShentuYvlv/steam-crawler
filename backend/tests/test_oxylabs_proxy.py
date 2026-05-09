import httpx
import pytest

from src.config import Config
from src.scrapers.comment_reply import DeveloperReplyClient
from src.utils.http_client import AsyncHttpClient
from src.utils.oxylabs_proxy import build_proxy_log_fields, load_oxylabs_proxy_settings
from src.utils.steam_rate_limiter import SteamRateLimiter


def _response(method: str, url: str, payload: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status_code=status_code, json=payload, request=request)


def _set_proxy_env(monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True) -> None:
    monkeypatch.setenv("OXYLABS_PROXY_ENABLED", "true" if enabled else "false")
    monkeypatch.setenv("OXYLABS_PROXY_HOST", "dc.oxylabs.io")
    monkeypatch.setenv("OXYLABS_PROXY_PORT", "8000")
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "user-zed00_NwCdm-country-US")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "123456789Nb=")
    monkeypatch.setenv("OXYLABS_PROXY_SCHEME", "https")
    monkeypatch.setenv("OXYLABS_PROXY_ROTATING_PORT", "8000")
    monkeypatch.setenv("OXYLABS_PROXY_SESSION_PORT_MIN", "8001")
    monkeypatch.setenv("OXYLABS_PROXY_SESSION_PORT_MAX", "63000")
    monkeypatch.setenv("OXYLABS_PROXY_DIRECT_FALLBACK", "true")


async def test_async_http_client_uses_rotating_proxy_port(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_proxy_env(monkeypatch, enabled=True)
    created_proxies: list[str | None] = []

    class FakeAsyncClient:
        def __init__(self, *, proxy=None, **kwargs):
            self.proxy = proxy
            created_proxies.append(proxy)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params=None):
            return _response("GET", url, {"success": 1})

        async def aclose(self):
            return None

    monkeypatch.setattr("src.utils.http_client.httpx.AsyncClient", FakeAsyncClient)

    config = Config()
    config.http.max_retries = 0
    client = AsyncHttpClient(config, proxy_mode="rotate_per_request")
    try:
        response = await client.get("https://example.com", delay=False)
    finally:
        await client.close()

    assert response.json()["success"] == 1
    assert any(proxy and proxy.endswith("@dc.oxylabs.io:8000") for proxy in created_proxies)


async def test_async_http_client_falls_back_to_direct_when_proxy_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_proxy_env(monkeypatch, enabled=True)
    created_proxies: list[str | None] = []

    class FakeAsyncClient:
        def __init__(self, *, proxy=None, **kwargs):
            self.proxy = proxy
            created_proxies.append(proxy)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params=None):
            if self.proxy is not None:
                raise httpx.ProxyError("proxy failed")
            return _response("GET", url, {"success": 1})

        async def aclose(self):
            return None

    monkeypatch.setattr("src.utils.http_client.httpx.AsyncClient", FakeAsyncClient)

    config = Config()
    config.http.max_retries = 0
    client = AsyncHttpClient(config, proxy_mode="rotate_per_request")
    try:
        response = await client.get("https://example.com", delay=False)
        metadata = client.get_last_request_metadata()
    finally:
        await client.close()

    assert response.json()["success"] == 1
    assert created_proxies[0] is not None
    assert created_proxies[-1] is None
    assert metadata["proxy_fallback_used"] is True
    assert metadata["proxy_error"] == "proxy failed"


async def test_async_http_client_falls_back_to_http_proxy_scheme_before_direct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_proxy_env(monkeypatch, enabled=True)
    created_proxies: list[str | None] = []

    class FakeAsyncClient:
        def __init__(self, *, proxy=None, **kwargs):
            self.proxy = proxy
            created_proxies.append(proxy)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params=None):
            if self.proxy is None:
                raise AssertionError("direct fallback should not be used")
            if str(self.proxy).startswith("https://"):
                raise httpx.ProxyError("[SSL] record layer failure (_ssl.c:1016)")
            return _response("GET", url, {"success": 1})

        async def aclose(self):
            return None

    monkeypatch.setattr("src.utils.http_client.httpx.AsyncClient", FakeAsyncClient)

    config = Config()
    config.http.max_retries = 0
    client = AsyncHttpClient(config, proxy_mode="rotate_per_request")
    try:
        response = await client.get("https://example.com", delay=False)
        metadata = client.get_last_request_metadata()
    finally:
        await client.close()

    assert response.json()["success"] == 1
    assert any(proxy and str(proxy).startswith("https://") for proxy in created_proxies)
    assert any(proxy and str(proxy).startswith("http://") for proxy in created_proxies)
    assert metadata["proxy_scheme"] == "http"
    assert metadata["proxy_fallback_used"] is False


async def test_async_http_client_raises_direct_error_when_proxy_and_direct_both_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_proxy_env(monkeypatch, enabled=True)

    class FakeAsyncClient:
        def __init__(self, *, proxy=None, **kwargs):
            self.proxy = proxy

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params=None):
            if self.proxy is not None:
                raise httpx.ProxyError("proxy failed")
            raise httpx.ReadTimeout("direct failed")

        async def aclose(self):
            return None

    monkeypatch.setattr("src.utils.http_client.httpx.AsyncClient", FakeAsyncClient)

    config = Config()
    config.http.max_retries = 0
    client = AsyncHttpClient(config, proxy_mode="rotate_per_request")
    try:
        with pytest.raises(httpx.ReadTimeout, match="direct failed"):
            await client.get("https://example.com", delay=False)
    finally:
        await client.close()


async def test_async_http_client_keeps_direct_path_when_proxy_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_proxy_env(monkeypatch, enabled=False)
    created_proxies: list[str | None] = []

    class FakeAsyncClient:
        def __init__(self, *, proxy=None, **kwargs):
            self.proxy = proxy
            created_proxies.append(proxy)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params=None):
            return _response("GET", url, {"success": 1})

        async def aclose(self):
            return None

    monkeypatch.setattr("src.utils.http_client.httpx.AsyncClient", FakeAsyncClient)

    config = Config()
    config.http.max_retries = 0
    client = AsyncHttpClient(config, proxy_mode="rotate_per_request")
    try:
        await client.get("https://example.com", delay=False)
    finally:
        await client.close()

    assert created_proxies == [None]


async def test_developer_reply_client_reuses_single_sticky_session_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_proxy_env(monkeypatch, enabled=True)
    monkeypatch.setattr("src.utils.oxylabs_proxy.random.randint", lambda start, end: 35467)
    created_proxies: list[str | None] = []

    class FakeAsyncClient:
        def __init__(self, *, proxy=None, **kwargs):
            self.proxy = proxy
            created_proxies.append(proxy)

        async def post(self, url, data=None):
            return _response("POST", url, {"success": 1})

        async def aclose(self):
            return None

    monkeypatch.setattr("src.scrapers.comment_reply.httpx.AsyncClient", FakeAsyncClient)

    client = DeveloperReplyClient("sessionid=abc")
    try:
        await client.set_developer_response("1001", "hello")
        await client.set_developer_response("1002", "world")
    finally:
        await client.close()

    proxied_clients = [proxy for proxy in created_proxies if proxy is not None]
    assert client.proxy_session_port == 35467
    assert proxied_clients == ["https://user-zed00_NwCdm-country-US:123456789Nb%3D@dc.oxylabs.io:35467"]


async def test_developer_reply_client_falls_back_to_http_sticky_proxy_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_proxy_env(monkeypatch, enabled=True)
    monkeypatch.setattr("src.utils.oxylabs_proxy.random.randint", lambda start, end: 35467)
    created_proxies: list[str | None] = []

    class FakeAsyncClient:
        def __init__(self, *, proxy=None, **kwargs):
            self.proxy = proxy
            created_proxies.append(proxy)

        async def post(self, url, data=None):
            if self.proxy is None:
                raise AssertionError("direct fallback should not be used")
            if str(self.proxy).startswith("https://"):
                raise httpx.ProxyError("[SSL] record layer failure (_ssl.c:1016)")
            return _response("POST", url, {"success": 1})

        async def aclose(self):
            return None

    monkeypatch.setattr("src.scrapers.comment_reply.httpx.AsyncClient", FakeAsyncClient)

    client = DeveloperReplyClient("sessionid=abc")
    try:
        result = await client.set_developer_response("1001", "hello")
        metadata = client.get_last_request_metadata()
    finally:
        await client.close()

    assert result["success"] is True
    assert any(proxy and str(proxy).startswith("https://") for proxy in created_proxies)
    assert any(proxy and str(proxy).startswith("http://") for proxy in created_proxies)
    assert metadata["proxy_scheme"] == "http"


async def test_probe_uses_same_rotating_proxy_strategy_as_scraping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_proxy_modes: list[str] = []

    class FakeProbeClient:
        def __init__(self, config, *, proxy_mode="none", **kwargs):
            captured_proxy_modes.append(proxy_mode)

        async def get_json(self, url, params=None, delay=True):
            return {"success": 1, "reviews": []}

        def get_last_request_metadata(self):
            return {
                "proxy_enabled": True,
                "proxy_mode": "rotate_per_request",
                "proxy_port_type": "rotating",
                "proxy_port": 8000,
                "proxy_fallback_enabled": True,
                "proxy_fallback_used": False,
                "proxy_error": None,
            }

        async def close(self):
            return None

    monkeypatch.setattr("src.utils.steam_rate_limiter.AsyncHttpClient", FakeProbeClient)

    limiter = SteamRateLimiter()
    result = await limiter.probe(
        app_id=998940,
        language="schinese",
        filter_type="recent",
        review_type="all",
        purchase_type="all",
        use_review_quality=True,
    )

    assert captured_proxy_modes == ["rotate_per_request"]
    assert result["ok"] is True
    assert result["proxy_mode"] == "rotate_per_request"
    assert result["proxy_port"] == 8000


def test_proxy_log_fields_do_not_include_plaintext_password(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_proxy_env(monkeypatch, enabled=True)
    settings = load_oxylabs_proxy_settings()
    fields = build_proxy_log_fields(
        "sticky_session",
        settings=settings,
        session_port=35467,
        fallback_used=True,
        proxy_error="proxy failed",
    )

    assert "123456789Nb=" not in repr(fields)
    assert "user-zed00_NwCdm-country-US" not in repr(fields)
