from __future__ import annotations

from app import metadata_source
from app.modules.metadata.interfaces import MetadataRepository


class SqliteMetadataRepository(MetadataRepository):
    """Thin adapter over the external read-only metadata SQLite database."""

    def load_records(self) -> list[dict]:
        return metadata_source.load_metadata_records()

    def load_image(self, metadata_id: int | None) -> dict | None:
        return metadata_source.load_metadata_image(metadata_id)
