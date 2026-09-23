from __future__ import annotations

from unittest.mock import patch

from app.repositories.sqlite_metadata.repository import SqliteMetadataRepository


def test_load_records_delegates_to_metadata_source():
    repo = SqliteMetadataRepository()
    with patch("app.metadata_source.load_metadata_records", return_value=[{"id": 1}]) as mocked:
        assert repo.load_records() == [{"id": 1}]
    mocked.assert_called_once_with()


def test_load_image_delegates_to_metadata_source():
    repo = SqliteMetadataRepository()
    with patch("app.metadata_source.load_metadata_image", return_value=None) as mocked:
        assert repo.load_image(42) is None
    mocked.assert_called_once_with(42)
