from __future__ import annotations

from typing import Any

from app.models import Exam, Patient, User
from app.repositories.interfaces.diagnosis_repository import DiagnosisRepository
from app.repositories.interfaces.exam_draft_repository import ExamDraftRepository
from app.repositories.interfaces.patient_repository import PatientRepository
from app.repositories.interfaces.review_repository import ReviewRepository
from app.services.diagnosis_payload_service import DiagnosisPayloadService
from app.services.validation_context_service import ValidationContext, ValidationContextService
from app.services.validation_queue_service import ValidationQueueService


class ExamPayloadService:
    def __init__(
        self,
        patient_repository: PatientRepository,
        review_repository: ReviewRepository,
        exam_draft_repository: ExamDraftRepository,
        diagnosis_repository: DiagnosisRepository,
        diagnosis_payload_service: DiagnosisPayloadService,
        validation_context_service: ValidationContextService,
        validation_queue_service: ValidationQueueService,
    ) -> None:
        self._patient_repository = patient_repository
        self._review_repository = review_repository
        self._exam_draft_repository = exam_draft_repository
        self._diagnosis_repository = diagnosis_repository
        self._diagnosis_payload_service = diagnosis_payload_service
        self._validation_context_service = validation_context_service
        self._validation_queue_service = validation_queue_service

    @staticmethod
    def _patient_payload(patient: Patient) -> dict:
        return {
            "id": patient.id,
            "birth_date": patient.birth_date,
            "age": patient.age or None,
            "sex": patient.sex or None,
            "weight": patient.weight or None,
            "height": patient.height or None,
            "bmi": patient.bmi or None,
        }

    def _review_timestamps(self, exam: Exam) -> tuple[Any, Any]:
        if exam.status_validation == "nao_validado":
            return None, None

        reviews = self._review_repository.list_for_exam(exam.id)

        if exam.status_validation == "em_validacao":
            started_at = next(
                (review.created_at for review in reviews if review.status_after == "em_validacao"),
                None,
            )
            return started_at, None

        completed_at = next(
            (review.created_at for review in reversed(reviews) if review.status_after == "valido"),
            None,
        )
        return None, completed_at

    def build(
        self,
        exam: Exam,
        include_details: bool = False,
        context: ValidationContext | None = None,
        current_user: User | None = None,
    ) -> dict[str, Any]:
        context = context or self._validation_context_service.active_context()
        patient = self._patient_repository.get(exam.patient_id)
        started_at, completed_at = self._review_timestamps(exam)
        payload = {
            "id": exam.id,
            "exam_code": exam.exam_code,
            "exam_date": exam.exam_date,
            "exam_time": exam.exam_time,
            "category": exam.category,
            "exam_type": exam.exam_type,
            "status_validation": exam.status_validation,
            "queue_state": self._validation_queue_service.exam_queue_state(exam, context),
            "review_result": exam.review_result if exam.status_validation == "valido" else None,
            "image_url": exam.image_url,
            "image_endpoint": f"/exams/{exam.id}/image",
            "comments": exam.comments,
            "source_notes": exam.source_notes,
            "created_at": exam.created_at,
            "updated_at": exam.updated_at,
            "started_at": started_at,
            "completed_at": completed_at,
            "patient": self._patient_payload(patient),
            "validation_context": context.as_dict(),
        }

        if current_user and current_user.id is not None:
            draft = self._exam_draft_repository.get_for_exam_and_reviewer(exam.id, current_user.id)
            payload["draft_notes"] = draft.notes if draft else None

        if include_details:
            ai_recommendations = self._validation_context_service.load_ai_recommendations()
            diagnoses = self._diagnosis_repository.list_for_exam(exam.id)
            payload["diagnoses"] = [
                self._diagnosis_payload_service.build(
                    diagnosis,
                    context=context,
                    exam_code=exam.exam_code,
                    ai_recommendations=ai_recommendations,
                )
                for diagnosis in diagnoses
            ]

        return payload
