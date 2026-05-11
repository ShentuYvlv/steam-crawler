from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

from src.utils.env_loader import load_env_defaults


ProxyMode = Literal["none", "rotate_per_request", "sticky_session"]
SUPPORTED_PROXY_SCHEMES = ("https", "http")


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value.strip())


@dataclass(frozen=True)
class OxylabsProxySettings:
    enabled: bool = False
    host: str = "dc.oxylabs.io"
    port: int = 8000
    username: str = ""
    password: str = ""
    scheme: str = "https"
    rotating_port: int = 8000
    session_port_min: int = 8001
    session_port_max: int = 63000
    direct_fallback: bool = True

    def validate(self) -> None:
        if not self.enabled:
            return
        if not self.host.strip():
            raise ValueError("OXYLABS_PROXY_HOST is required when OXYLABS_PROXY_ENABLED=true")
        if not self.username.strip():
            raise ValueError("OXYLABS_PROXY_USERNAME is required when OXYLABS_PROXY_ENABLED=true")
        if not self.password:
            raise ValueError("OXYLABS_PROXY_PASSWORD is required when OXYLABS_PROXY_ENABLED=true")
        if self.rotating_port != 8000:
            raise ValueError("OXYLABS_PROXY_ROTATING_PORT must be 8000")
        if self.session_port_min < 8001 or self.session_port_max > 63000:
            raise ValueError("OXYLABS proxy sticky session ports must stay within 8001..63000")
        if self.session_port_min > self.session_port_max:
            raise ValueError("OXYLABS_PROXY_SESSION_PORT_MIN cannot exceed OXYLABS_PROXY_SESSION_PORT_MAX")

    def is_active_for_mode(self, proxy_mode: ProxyMode) -> bool:
        return self.enabled and proxy_mode != "none"

    def choose_sticky_session_port(self) -> int:
        self.validate()
        return random.randint(self.session_port_min, self.session_port_max)

    def _scheme_candidates(self, preferred_scheme: str | None = None) -> list[str]:
        primary = (preferred_scheme or self.scheme or "https").strip().lower()
        candidates: list[str] = []
        for scheme in (primary, *SUPPORTED_PROXY_SCHEMES):
            if scheme and scheme not in candidates:
                candidates.append(scheme)
        return candidates

    def build_proxy_url(self, *, port: int, scheme_override: str | None = None) -> str:
        self.validate()
        username = quote(self.username, safe="")
        password = quote(self.password, safe="")
        scheme = (scheme_override or self.scheme).strip().lower()
        return f"{scheme}://{username}:{password}@{self.host}:{port}"

    def build_rotating_proxy_url(self, *, scheme_override: str | None = None) -> str:
        return self.build_proxy_url(port=self.rotating_port, scheme_override=scheme_override)

    def build_sticky_proxy_url(
        self,
        *,
        session_port: int,
        scheme_override: str | None = None,
    ) -> str:
        return self.build_proxy_url(port=session_port, scheme_override=scheme_override)

    def proxy_url_candidates(
        self,
        proxy_mode: ProxyMode,
        *,
        session_port: int | None = None,
    ) -> list[tuple[str, str]]:
        if proxy_mode == "none":
            return []
        port = self.rotating_port if proxy_mode == "rotate_per_request" else session_port
        if port is None:
            raise ValueError("Sticky session proxy candidates require a session port")
        return [
            (scheme, self.build_proxy_url(port=port, scheme_override=scheme))
            for scheme in self._scheme_candidates()
        ]


def load_oxylabs_proxy_settings() -> OxylabsProxySettings:
    load_env_defaults()
    settings = OxylabsProxySettings(
        enabled=_parse_bool(os.environ.get("OXYLABS_PROXY_ENABLED"), default=False),
        host=os.environ.get("OXYLABS_PROXY_HOST", "dc.oxylabs.io").strip(),
        port=_parse_int(os.environ.get("OXYLABS_PROXY_PORT"), 8000),
        username=os.environ.get("OXYLABS_PROXY_USERNAME", "").strip(),
        password=os.environ.get("OXYLABS_PROXY_PASSWORD", ""),
        scheme=os.environ.get("OXYLABS_PROXY_SCHEME", "https").strip() or "https",
        rotating_port=_parse_int(os.environ.get("OXYLABS_PROXY_ROTATING_PORT"), 8000),
        session_port_min=_parse_int(os.environ.get("OXYLABS_PROXY_SESSION_PORT_MIN"), 8001),
        session_port_max=_parse_int(os.environ.get("OXYLABS_PROXY_SESSION_PORT_MAX"), 63000),
        direct_fallback=_parse_bool(os.environ.get("OXYLABS_PROXY_DIRECT_FALLBACK"), default=True),
    )
    settings.validate()
    return settings


def build_proxy_log_fields(
    proxy_mode: ProxyMode,
    *,
    settings: OxylabsProxySettings | None = None,
    session_port: int | None = None,
    proxy_scheme: str | None = None,
    fallback_used: bool = False,
    proxy_error: Exception | str | None = None,
) -> dict[str, Any]:
    proxy_settings = settings or load_oxylabs_proxy_settings()
    port_type = "none"
    port_value: int | None = None
    scheme_value: str | None = None
    if proxy_settings.is_active_for_mode(proxy_mode):
        if proxy_mode == "rotate_per_request":
            port_type = "rotating"
            port_value = proxy_settings.rotating_port
        elif proxy_mode == "sticky_session":
            port_type = "sticky_session"
            port_value = session_port
        scheme_value = (proxy_scheme or proxy_settings.scheme).strip().lower()

    error_message: str | None = None
    if proxy_error is not None:
        error_message = proxy_error if isinstance(proxy_error, str) else (str(proxy_error) or type(proxy_error).__name__)

    return {
        "proxy_enabled": proxy_settings.is_active_for_mode(proxy_mode),
        "proxy_mode": proxy_mode,
        "proxy_port_type": port_type,
        "proxy_port": port_value,
        "proxy_scheme": scheme_value,
        "proxy_host": proxy_settings.host if proxy_settings.is_active_for_mode(proxy_mode) else None,
        "proxy_fallback_enabled": proxy_settings.direct_fallback,
        "proxy_fallback_used": fallback_used,
        "proxy_error": error_message,
    }
