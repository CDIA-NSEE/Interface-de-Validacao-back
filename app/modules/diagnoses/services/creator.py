from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.auth.models import User
from app.modules.diagnoses.models import Diagnosis, DiagnosisRegion
from app.modules.diagnoses.repositories.interfaces import DiagnosisRegionRepository, DiagnosisRepository
from app.modules.diagnoses.schemas import DiagnosisCreate, DiagnosisRegionPayload
from app.modules.diagnoses.services.options_service import DiagnosisOptionsService
from app.modules.diagnoses.services.payload_service import DiagnosisPayloadService
from app.modules.diagnoses.services.region_shared import sync_legacy_region_fields, validate_region_payload
from app.modules.diagnoses.services.standardizer import DiagnosisStandardizer
from app.modules.exams.repositories.interfaces import ExamRepository


class DiagnosisCreator:
    def __init__(
        self,
        diagnosis_repository: DiagnosisRepository,
        diagnosis_region_repository: DiagnosisRegionRepository,
        exam_repository: ExamRepository,
        diagnosis_standardizer: DiagnosisStandardizer,
        diagnosis_options_service: DiagnosisOptionsService,
        diagnosis_payload_service: DiagnosisPayloadService,
    ) -> None:
        self._diagnosis_repository = diagnosis_repository
        self._diagnosis_region_repository = diagnosis_region_repository
        self._exam_repository = exam_repository
        self._diagnosis_standardizer = diagnosis_standardizer
        self._diagnosis_options_service = diagnosis_options_service
        self._diagnosis_payload_service = diagnosis_payload_service

    @staticmethod
    def _region_input_from_payload(payload: DiagnosisCreate) -> DiagnosisRegionPayload | None:
        if (
            payload.region_x is None
            or payload.region_y is None
            or payload.region_width is None
            or payload.region_height is None
        ):
            return None

        return DiagnosisRegionPayload(
            x=payload.region_x,
            y=payload.region_y,
            width=payload.region_width,
            height=payload.region_height,
        )

    def create(self, exam_id: int, payload: DiagnosisCreate, current_user: User) -> dict[str, Any]:
        exam = self._exam_repository.get(exam_id)
        if not exam:
            raise NotFoundError("Exame não encontrado.")

        requested_diagnosis_name = payload.name.strip()
        if not requested_diagnosis_name:
            raise ValidationError("O nome do diagnóstico é obrigatório.")

        allowed_names = set(self._diagnosis_options_service.load_diagnosis_options())
        diagnosis_name = self._diagnosis_standardizer.standardize(requested_diagnosis_name)
        if diagnosis_name not in allowed_names:
            raise ValidationError("Selecione um diagnóstico padronizado.")

        region_payload = self._region_input_from_payload(payload)
        if region_payload:
            validate_region_payload(region_payload)

        requires_region = self._diagnosis_standardizer.requires_region(
            diagnosis_name, requested_diagnosis_name
        )
        initial_review_status = "confirmed" if region_payload or not requires_region else "pending"
        diagnosis = Diagnosis(
            exam_id=exam_id,
            name=diagnosis_name,
            source="doctor_added",
            review_status=initial_review_status,
            is_abnormal=payload.is_abnormal,
        )
        self._diagnosis_repository.add(diagnosis)
        self._diagnosis_repository.flush()

        if region_payload:
            self._diagnosis_region_repository.add(
                DiagnosisRegion(
                    exam_id=exam_id,
                    diagnosis_id=diagnosis.id,
                    x=region_payload.x,
                    y=region_payload.y,
                    width=region_payload.width,
                    height=region_payload.height,
                    created_by_id=current_user.id,
                    created_by_name=current_user.full_name,
                )
            )
            sync_legacy_region_fields(self._diagnosis_region_repository, diagnosis)

        exam.updated_at = datetime.now(UTC)
        self._exam_repository.save(exam)

        self._diagnosis_repository.commit()
        self._diagnosis_repository.refresh(diagnosis)
        return self._diagnosis_payload_service.build(diagnosis, exam_code=exam.exam_code)
