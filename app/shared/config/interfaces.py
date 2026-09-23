from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ConfigRepository(ABC):
    """Read-only adapter over the JSON files under ``app/config``."""

    @abstractmethod
    def load_json(self, name: str, default: Any) -> Any: ...
