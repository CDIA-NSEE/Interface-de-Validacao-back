from __future__ import annotations

from typing import Any, Protocol


class CacheClient(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
