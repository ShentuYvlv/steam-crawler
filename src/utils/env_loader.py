from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_env_defaults(*paths: str | Path) -> dict[str, str]:
    env_paths = list(paths) if paths else [REPO_ROOT / ".env"]
    loaded: dict[str, str] = {}
    for env_path in env_paths:
        values = parse_env_file(env_path)
        loaded.update(values)
        for key, value in values.items():
            os.environ.setdefault(key, value)
    return loaded
