from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.auth.models import User
from app.modules.diagnoses.models import DiagnosisValidation
from app.modules.diagnoses.repositories.interfaces import DiagnosisRepository, DiagnosisValidationRepository
from app.modules.diagnoses.schemas import DiagnosisReview
from app.modules.diagnoses.services.payload_service import DiagnosisPayloadService
from app.modules.diagnoses.services.standardizer import DiagnosisStandardizer
from app.modules.exams.models import Review
from app.modules.exams.repositories.interfaces import ExamRepository, ReviewRepository
from app.modules.exams.services.payload_service import ExamPayloadService
from app.modules.validation.services.context_service import ValidationContextService


class DiagnosisReviewService:
    def __init__(
        self,
        diagnosis_repository: DiagnosisRepository,
        exam_repository: ExamRepository,
        review_repository: ReviewRepository,
        diagnosis_validation_repository: DiagnosisValidationRepository,
        diagnosis_standardizer: DiagnosisStandardizer,
        diagnosis_payload_service: DiagnosisPayloadService,
        exam_payload_service: ExamPayloadService,
        validation_context_service: ValidationContextService,
    ) -> None:
        self._diagnosis_repository = diagnosis_repository
        self._exam_repository = exam_repository
        self._review_repository = review_repository
        self._diagnosis_validation_repository = diagnosis_validation_repository
        self._diagnosis_standardizer = diagnosis_standardizer
        self._diagnosis_payload_service = diagnosis_payload_service
        self._exam_payload_service = exam_payload_service
        self._validation_context_service = validation_context_service

    def review_diagnosis(self, exam_id: int, diagnosis_id: int, payload: DiagnosisReview) -> dict[str, Any]:
        exam = self._exam_repository.get(exam_id)
        if not exam:
            raise NotFoundError("Exame não encontrado.")

        diagnosis = self._diagnosis_repository.get(diagnosis_id)
        if not diagnosis or diagnosis.exam_id != exam_id:
            raise NotFoundError("Diagnóstico não encontrado.")

        if diagnosis.source != "original":
            raise ValidationError("Somente diagnósticos originais podem ser confirmados ou rejeitados.")

        if payload.review_status == "confirmed":
            self._diagnosis_payload_service.ensure_region_before_confirm(diagnosis)

        diagnosis.review_status = payload.review_status
        exam.updated_at = datetime.now(UTC)
        self._diagnosis_repository.save(diagnosis)
        self._exam_repository.save(exam)
        self._diagnosis_repository.commit()
        self._diagnosis_repository.refresh(diagnosis)

        return self._diagnosis_payload_service.build(diagnosis, exam_code=exam.exam_code)

    def review_validation_diagnosis(
        self, diagnosis_id: int, payload: DiagnosisReview, current_user: User
    ) -> dict[str, Any]:
        diagnosis = self._diagnosis_repository.get(diagnosis_id)
        if not diagnosis:
            raise NotFoundError("Diagnostico nao encontrado.")

        exam = self._exam_repository.get(diagnosis.exam_id)
        if not exam:
            raise NotFoundError("Exame não encontrado.")

        context = self._validation_context_service.active_context()
        standard_text = self._diagnosis_standardizer.standardize(diagnosis.name)
        if payload.review_status == "confirmed":
            self._diagnosis_payload_service.ensure_region_before_confirm(diagnosis)

        now = datetime.now(UTC)
        validation = self._diagnosis_payload_service.latest_standard_validation(
            exam.id, standard_text, context.cycle_key
        )

        if validation:
            validation.diagnosis_id = diagnosis.id
            validation.review_status = payload.review_status
            validation.reviewer_id = current_user.id
            validation.reviewer_name = current_user.full_name
            validation.notes = payload.notes
            validation.day_index = context.day_index
            validation.updated_at = now
        else:
            validation = DiagnosisValidation(
                exam_id=exam.id,
                diagnosis_id=diagnosis.id,
                standard_text=standard_text,
                cycle_key=context.cycle_key,
                day_index=context.day_index,
                review_status=payload.review_status,
                reviewer_id=current_user.id,
                reviewer_name=current_user.full_name,
                notes=payload.notes,
                created_at=now,
                updated_at=now,
            )

        diagnosis.review_status = payload.review_status
        status_before = exam.status_validation
        if exam.status_validation == "nao_validado":
            exam.status_validation = "em_validacao"
            self._review_repository.add(
                Review(
                    exam_id=exam.id,
                    doctor_name=current_user.full_name,
                    status_before=status_before,
                    status_after="em_validacao",
                    created_at=now,
                )
            )

        exam.updated_at = now
        self._diagnosis_validation_repository.save(validation)
        self._diagnosis_repository.save(diagnosis)
        self._exam_repository.save(exam)
        self._exam_repository.commit()
        self._exam_repository.refresh(exam)

        return self._exam_payload_service.build(
            exam, include_details=True, context=context, current_user=current_user
        )
