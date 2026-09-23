from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import NotFoundError
from app.modules.diagnoses.repositories.interfaces import DiagnosisRegionRepository, DiagnosisRepository
from app.modules.diagnoses.schemas import DiagnosisRegionPayload
from app.modules.diagnoses.services.payload_service import DiagnosisPayloadService
from app.modules.diagnoses.services.region_shared import sync_legacy_region_fields, validate_region_payload
from app.modules.exams.repositories.interfaces import ExamRepository


class DiagnosisRegionUpdater:
    def __init__(
        self,
        diagnosis_repository: DiagnosisRepository,
        diagnosis_region_repository: DiagnosisRegionRepository,
        exam_repository: ExamRepository,
        diagnosis_payload_service: DiagnosisPayloadService,
    ) -> None:
        self._diagnosis_repository = diagnosis_repository
        self._diagnosis_region_repository = diagnosis_region_repository
        self._exam_repository = exam_repository
        self._diagnosis_payload_service = diagnosis_payload_service

    def update(self, diagnosis_id: int, region_id: int, payload: DiagnosisRegionPayload) -> dict[str, Any]:
        validate_region_payload(payload)

        diagnosis = self._diagnosis_repository.get(diagnosis_id)
        if not diagnosis:
            raise NotFoundError("Diagnostico nao encontrado.")

        region = self._diagnosis_region_repository.get(region_id)
        if not region or region.diagnosis_id != diagnosis_id:
            raise NotFoundError("Area do diagnostico nao encontrada.")

        region.x = payload.x
        region.y = payload.y
        region.width = payload.width
        region.height = payload.height
        region.updated_at = datetime.now(UTC)
        self._diagnosis_region_repository.save(region)
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
