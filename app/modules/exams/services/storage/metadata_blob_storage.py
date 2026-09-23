from __future__ import annotations

from app.modules.exams.models import Exam
from app.modules.metadata.interfaces import MetadataRepository


class MetadataBlobImageStorage:
    """Default image storage: reads image blobs from the external metadata SQLite db."""

    def __init__(self, metadata_repository: MetadataRepository) -> None:
        self._metadata_repository = metadata_repository

    def get_image(self, exam: Exam) -> dict | None:
        return self._metadata_repository.load_image(exam.metadata_id)
