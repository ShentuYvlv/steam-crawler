"""Shared utility exports."""

__all__ = ["HttpClient", "Checkpoint"]


def __getattr__(name: str):
    if name == "HttpClient":
        from src.utils.http_client import HttpClient

        return HttpClient
    if name == "Checkpoint":
        from src.utils.checkpoint import Checkpoint

        return Checkpoint
    raise AttributeError(name)
