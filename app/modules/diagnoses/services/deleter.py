from __future__ import annotations

from datetime import UTC, datetime

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.diagnoses.repositories.interfaces import DiagnosisRegionRepository, DiagnosisRepository
from app.modules.exams.repositories.interfaces import ExamRepository


class DiagnosisDeleter:
    def __init__(
        self,
        diagnosis_repository: DiagnosisRepository,
        diagnosis_region_repository: DiagnosisRegionRepository,
        exam_repository: ExamRepository,
    ) -> None:
        self._diagnosis_repository = diagnosis_repository
        self._diagnosis_region_repository = diagnosis_region_repository
        self._exam_repository = exam_repository

    def delete(self, exam_id: int, diagnosis_id: int) -> int:
        exam = self._exam_repository.get(exam_id)
        if not exam:
            raise NotFoundError("Exame não encontrado.")

        diagnosis = self._diagnosis_repository.get(diagnosis_id)
        if not diagnosis or diagnosis.exam_id != exam_id:
            raise NotFoundError("Diagnóstico não encontrado.")

        if diagnosis.source == "original":
            raise ValidationError("O diagnóstico original do ECG não pode ser removido.")

        for region in self._diagnosis_region_repository.list_for_diagnosis(diagnosis.id):
            self._diagnosis_region_repository.delete(region)
        self._diagnosis_repository.delete(diagnosis)

        exam.updated_at = datetime.now(UTC)
        self._exam_repository.save(exam)

        self._exam_repository.commit()
        return diagnosis_id
