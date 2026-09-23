from __future__ import annotations

from typing import Any

from app.shared.cache.interfaces import CacheClient
from app.shared.config.interfaces import ConfigRepository

_CACHE_KEY_PREFIX = "config_json:v1:"


class CachedConfigRepository(ConfigRepository):
    """Decorates a ConfigRepository with a cache lookup, avoiding disk reads per request."""

    def __init__(self, inner: ConfigRepository, cache_client: CacheClient, cache_ttl_seconds: int) -> None:
        self._inner = inner
        self._cache_client = cache_client
        self._cache_ttl_seconds = cache_ttl_seconds

    def load_json(self, name: str, default: Any) -> Any:
        cache_key = f"{_CACHE_KEY_PREFIX}{name}"
        cached = self._cache_client.get(cache_key)
        if cached is not None:
            return cached

        value = self._inner.load_json(name, default)
        self._cache_client.set(cache_key, value, self._cache_ttl_seconds)
        return value
