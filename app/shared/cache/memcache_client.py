from __future__ import annotations

import pickle
from typing import Any

from pymemcache.client.base import Client


class MemcacheClient:
    def __init__(self, server_url: str) -> None:
        host, _, port = server_url.rpartition(":")
        self._client = Client((host or "localhost", int(port) if port else 11211))

    def get(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return pickle.loads(raw)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._client.set(key, pickle.dumps(value), expire=ttl_seconds)
