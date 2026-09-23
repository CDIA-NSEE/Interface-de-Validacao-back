from __future__ import annotations

import json

from app.repositories.json_config_repository import JsonConfigRepository


def test_load_json_returns_parsed_content(tmp_path):
    config_file = tmp_path / "sample.json"
    config_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")

    repo = JsonConfigRepository(tmp_path)
    assert repo.load_json("sample.json", {}) == {"key": "value"}


def test_load_json_returns_default_when_missing(tmp_path):
    repo = JsonConfigRepository(tmp_path)
    default = {"fallback": True}
    assert repo.load_json("missing.json", default) == default
