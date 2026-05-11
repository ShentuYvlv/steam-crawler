from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


LOCATION_URL = "https://ip.oxylabs.io/location"


def _format_proxy_error(proxy_error: Exception | str | None) -> str | None:
    if proxy_error is None:
        return None
    return proxy_error if isinstance(proxy_error, str) else (str(proxy_error) or type(proxy_error).__name__)


def _parse_proxy_url(proxy_url: str) -> tuple[str | None, str | None, int | None]:
    parsed = urlparse(proxy_url.strip())
    scheme = parsed.scheme or None
    host = parsed.hostname
    try:
        port = parsed.port
    except ValueError:
        port = None
    return scheme, host, port


def build_explicit_proxy_log_fields(
    proxy_url: str | None,
    *,
    fallback_enabled: bool,
    fallback_used: bool = False,
    proxy_error: Exception | str | None = None,
) -> dict[str, Any]:
    if not proxy_url or not proxy_url.strip():
        return {
            "proxy_enabled": False,
            "proxy_mode": "none",
            "proxy_port_type": "none",
            "proxy_port": None,
            "proxy_scheme": None,
            "proxy_host": None,
            "proxy_fallback_enabled": fallback_enabled,
            "proxy_fallback_used": fallback_used,
            "proxy_error": _format_proxy_error(proxy_error),
        }

    scheme, host, port = _parse_proxy_url(proxy_url)
    return {
        "proxy_enabled": True,
        "proxy_mode": "explicit_proxy",
        "proxy_port_type": "explicit",
        "proxy_port": port,
        "proxy_scheme": scheme,
        "proxy_host": host,
        "proxy_fallback_enabled": fallback_enabled,
        "proxy_fallback_used": fallback_used,
        "proxy_error": _format_proxy_error(proxy_error),
    }


async def probe_proxy_location(
    proxy_url: str | None,
    *,
    fallback_enabled: bool,
    existing_client: httpx.AsyncClient | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    base = build_explicit_proxy_log_fields(
        proxy_url,
        fallback_enabled=fallback_enabled,
    )

    if not proxy_url or not proxy_url.strip():
        return {
            **base,
            "ok": False,
            "exact_ip": False,
            "note": "Proxy URL is not configured.",
            "location": None,
        }

    note = "Explicit proxy URL reused for the Steam developer reply session."
    if existing_client is not None:
        try:
            response = await existing_client.get(LOCATION_URL)
            response.raise_for_status()
            payload = response.json()
            return {
                **base,
                "ok": True,
                "exact_ip": True,
                "note": note,
                "location": payload,
            }
        except Exception as exc:
            return {
                **base,
                "ok": False,
                "exact_ip": True,
                "note": note,
                "location": None,
                "proxy_error": _format_proxy_error(exc),
            }

    try:
        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=httpx.Timeout(timeout_seconds),
            verify=False,
        ) as client:
            response = await client.get(LOCATION_URL)
            response.raise_for_status()
            payload = response.json()
            return {
                **base,
                "ok": True,
                "exact_ip": True,
                "note": note,
                "location": payload,
            }
    except Exception as exc:
        return {
            **base,
            "ok": False,
            "exact_ip": True,
            "note": note,
            "location": None,
            "proxy_error": _format_proxy_error(exc),
        }
