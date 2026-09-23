from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.modules.exams.repositories.interfaces import ExamRepository
from app.modules.exams.services.storage.interfaces import ImageStorage


class ExamImageService:
    def __init__(self, exam_repository: ExamRepository, image_storage: ImageStorage) -> None:
        self._exam_repository = exam_repository
        self._image_storage = image_storage

    def get_image(self, exam_id: int) -> dict:
        exam = self._exam_repository.get(exam_id)
        if not exam:
            raise NotFoundError("Exame não encontrado.")

        image = self._image_storage.get_image(exam)
        if image:
            return {"kind": "content", "content": image["content"], "media_type": image["media_type"]}

        return {"kind": "redirect", "url": exam.image_url or "/sample-ecg.svg"}
