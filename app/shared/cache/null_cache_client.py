from __future__ import annotations

from typing import Any


class NullCacheClient:
    """No-op cache used when caching is disabled or in tests."""

    def get(self, key: str) -> Any | None:
        return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        return None
