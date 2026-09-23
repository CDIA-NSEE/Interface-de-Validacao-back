from __future__ import annotations

from typing import Protocol

from app.modules.exams.models import Exam


class ExamImage(Protocol):
    content: bytes
    media_type: str


class ImageStorage(Protocol):
    def get_image(self, exam: Exam) -> dict | None:
        """Return {"content": bytes, "media_type": str} or None if no stored image."""
        ...
