from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.models import Review, User
from app.repositories.interfaces.exam_draft_repository import ExamDraftRepository
from app.repositories.interfaces.exam_repository import ExamRepository
from app.repositories.interfaces.review_repository import ReviewRepository
from app.schemas import ExamValidate, StatusUpdate
from app.services.exam_payload_service import ExamPayloadService


class ExamStatusService:
    def __init__(
        self,
        exam_repository: ExamRepository,
        review_repository: ReviewRepository,
        exam_draft_repository: ExamDraftRepository,
        exam_payload_service: ExamPayloadService,
    ) -> None:
        self._exam_repository = exam_repository
        self._review_repository = review_repository
        self._exam_draft_repository = exam_draft_repository
        self._exam_payload_service = exam_payload_service

    def update_status(self, exam_id: int, payload: StatusUpdate, current_user: User) -> dict[str, Any]:
        if payload.status_validation == "valido":
            raise ValidationError("Use /validate para validar um exame e informar review_result.")

        exam = self._exam_repository.get(exam_id)
        if not exam:
            raise NotFoundError("Exame não encontrado.")

        status_before = exam.status_validation
        exam.status_validation = payload.status_validation
        exam.review_result = None
        exam.updated_at = datetime.now(UTC)
        self._exam_repository.save(exam)

        if status_before != payload.status_validation:
            self._review_repository.add(
                Review(
                    exam_id=exam.id,
                    doctor_name=current_user.full_name,
                    status_before=status_before,
                    status_after=payload.status_validation,
                    created_at=exam.updated_at,
                )
            )

        self._exam_repository.commit()
        self._exam_repository.refresh(exam)
        return self._exam_payload_service.build(exam, include_details=True, current_user=current_user)

    def validate(self, exam_id: int, payload: ExamValidate, current_user: User) -> dict[str, Any]:
        exam = self._exam_repository.get(exam_id)
        if not exam:
            raise NotFoundError("Exame não encontrado.")

        draft = self._exam_draft_repository.get_for_exam_and_reviewer(exam.id, current_user.id)
        status_before = exam.status_validation
        now = datetime.now(UTC)
        review_notes = payload.notes if payload.notes is not None else (draft.notes if draft else None)

        exam.status_validation = "valido"
        exam.review_result = payload.review_result
        exam.updated_at = now
        self._exam_repository.save(exam)

        self._review_repository.add(
            Review(
                exam_id=exam.id,
                doctor_name=current_user.full_name,
                status_before=status_before,
                status_after="valido",
                review_result=payload.review_result,
                notes=review_notes,
                created_at=now,
            )
        )
        if draft:
            self._exam_draft_repository.delete(draft)

        self._exam_repository.commit()
        self._exam_repository.refresh(exam)
        return self._exam_payload_service.build(exam, include_details=True, current_user=current_user)
