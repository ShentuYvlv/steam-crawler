from __future__ import annotations

from typing import Any

import httpx

from src.utils.oxylabs_proxy import (
    ProxyMode,
    build_proxy_log_fields,
    load_oxylabs_proxy_settings,
)


LOCATION_URL = "https://ip.oxylabs.io/location"


async def fetch_proxy_location(
    proxy_mode: ProxyMode,
    *,
    session_port: int | None = None,
    proxy_scheme: str | None = None,
    existing_client: httpx.AsyncClient | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    settings = load_oxylabs_proxy_settings()
    base = build_proxy_log_fields(
        proxy_mode,
        settings=settings,
        session_port=session_port,
        proxy_scheme=proxy_scheme,
    )
    exact_ip = proxy_mode == "sticky_session"
    note = (
        "Same sticky-session proxy client; IP matches the Steam send session."
        if exact_ip
        else "Rotating proxy mode samples a current proxy IP only; it does not prove the exact IP used by a Steam request."
    )

    if not settings.is_active_for_mode(proxy_mode):
        return {
            **base,
            "ok": False,
            "exact_ip": False,
            "note": "Proxy is disabled for this mode.",
            "location": None,
        }

    if existing_client is not None:
        try:
            response = await existing_client.get(LOCATION_URL)
            response.raise_for_status()
            payload = response.json()
            return {
                **base,
                "ok": True,
                "exact_ip": exact_ip,
                "note": note,
                "location": payload,
            }
        except Exception as exc:
            return {
                **base,
                "ok": False,
                "exact_ip": exact_ip,
                "note": note,
                "location": None,
                "proxy_error": str(exc) or type(exc).__name__,
            }

    last_error: Exception | None = None
    for proxy_scheme, proxy_url in settings.proxy_url_candidates(
        proxy_mode,
        session_port=session_port,
    ):
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
                    "proxy_scheme": proxy_scheme,
                    "ok": True,
                    "exact_ip": exact_ip,
                    "note": note,
                    "location": payload,
                }
        except Exception as exc:
            last_error = exc
    error_message = None
    if last_error is not None:
        error_message = str(last_error) or type(last_error).__name__
    return {
        **base,
        "ok": False,
        "exact_ip": exact_ip,
        "note": note,
        "location": None,
        "proxy_error": error_message,
    }
