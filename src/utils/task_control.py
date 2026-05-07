from __future__ import annotations


class TaskCancelledError(RuntimeError):
    def __init__(self, message: str = "Task cancelled") -> None:
        super().__init__(message)
