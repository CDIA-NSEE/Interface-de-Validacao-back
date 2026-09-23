from __future__ import annotations

from app.repositories.cached_config_repository import CachedConfigRepository
from app.services.cache.null_cache_client import NullCacheClient


class RecordingConfigRepository:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def load_json(self, name, default):
        self.calls += 1
        return self.value


class DictCacheClient:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl_seconds):
        self.store[key] = value


def test_cached_config_repository_caches_after_first_read():
    inner = RecordingConfigRepository({"a": 1})
    repo = CachedConfigRepository(inner, DictCacheClient(), 300)

    assert repo.load_json("x.json", {}) == {"a": 1}
    assert repo.load_json("x.json", {}) == {"a": 1}
    assert inner.calls == 1


def test_cached_config_repository_null_cache_always_recomputes():
    inner = RecordingConfigRepository({"a": 1})
    repo = CachedConfigRepository(inner, NullCacheClient(), 300)

    repo.load_json("x.json", {})
    repo.load_json("x.json", {})

    assert inner.calls == 2


def test_cached_config_repository_different_keys_cached_separately():
    inner = RecordingConfigRepository({"a": 1})
    cache = DictCacheClient()
    repo = CachedConfigRepository(inner, cache, 300)

    repo.load_json("x.json", {})
    repo.load_json("y.json", {})

    assert inner.calls == 2
    assert len(cache.store) == 2
