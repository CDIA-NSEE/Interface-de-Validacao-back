from __future__ import annotations

from abc import ABC, abstractmethod


class MetadataRepository(ABC):
    """Read-only adapter over the external metadata SQLite database.

    Deliberately does NOT inherit the generic ``Repository`` base: this
    aggregate has no add/save/delete/commit surface.
    """

    @abstractmethod
    def load_records(self) -> list[dict]: ...

    @abstractmethod
    def load_image(self, metadata_id: int | None) -> dict | None: ...
