from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.shared.config.interfaces import ConfigRepository


class JsonConfigRepository(ConfigRepository):
    """Raw JSON reader over ``app/config`` — no business logic, just file access."""

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir

    def load_json(self, name: str, default: Any) -> Any:
        path = self._config_dir / name
        if not path.exists():
            return default

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
