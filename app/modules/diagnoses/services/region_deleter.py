from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.diagnoses.repositories.interfaces import DiagnosisRegionRepository, DiagnosisRepository
from app.modules.diagnoses.services.payload_service import DiagnosisPayloadService
from app.modules.diagnoses.services.region_shared import sync_legacy_region_fields
from app.modules.diagnoses.services.standardizer import DiagnosisStandardizer
from app.modules.exams.repositories.interfaces import ExamRepository


class DiagnosisRegionDeleter:
    def __init__(
        self,
        diagnosis_repository: DiagnosisRepository,
        diagnosis_region_repository: DiagnosisRegionRepository,
        exam_repository: ExamRepository,
        diagnosis_standardizer: DiagnosisStandardizer,
        diagnosis_payload_service: DiagnosisPayloadService,
    ) -> None:
        self._diagnosis_repository = diagnosis_repository
        self._diagnosis_region_repository = diagnosis_region_repository
        self._exam_repository = exam_repository
        self._diagnosis_standardizer = diagnosis_standardizer
        self._diagnosis_payload_service = diagnosis_payload_service

    def delete(self, diagnosis_id: int, region_id: int) -> dict[str, Any]:
        diagnosis = self._diagnosis_repository.get(diagnosis_id)
        if not diagnosis:
            raise NotFoundError("Diagnostico nao encontrado.")

        region = self._diagnosis_region_repository.get(region_id)
        if not region or region.diagnosis_id != diagnosis_id:
            raise NotFoundError("Area do diagnostico nao encontrada.")

        regions = self._diagnosis_payload_service.diagnosis_region_payloads(diagnosis)
        standard_text = self._diagnosis_standardizer.standardize(diagnosis.name)
        if (
            len(regions) <= 1
            and self._diagnosis_standardizer.requires_region(standard_text, diagnosis.name)
            and self._diagnosis_payload_service.effective_review_status(diagnosis) == "confirmed"
        ):
            raise ValidationError("Nao e possivel remover a ultima area de um infarto confirmado.")

        self._diagnosis_region_repository.delete(region)
        self._diagnosis_region_repository.flush()
        sync_legacy_region_fields(self._diagnosis_region_repository, diagnosis)

        exam = self._exam_repository.get(diagnosis.exam_id)
        if not exam:
            raise NotFoundError("Exame não encontrado.")
        exam.updated_at = datetime.now(UTC)

        self._diagnosis_repository.save(diagnosis)
        self._exam_repository.save(exam)
        self._diagnosis_repository.commit()
        self._diagnosis_repository.refresh(diagnosis)

        return self._diagnosis_payload_service.build(diagnosis, exam_code=exam.exam_code)
