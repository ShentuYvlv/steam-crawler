from __future__ import annotations

import traceback
from typing import Any


def format_exception_message(exc: BaseException) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def format_exception_details(exc: BaseException) -> dict[str, Any]:
    return {
        "error": format_exception_message(exc),
        "exception_type": exc.__class__.__name__,
        "exception_repr": repr(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).strip(),
    }
