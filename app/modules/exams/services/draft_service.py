from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import NotFoundError
from app.models import ExamDraft, User
from app.repositories.interfaces.exam_draft_repository import ExamDraftRepository
from app.repositories.interfaces.exam_repository import ExamRepository
from app.schemas import ExamDraftUpdate
from app.services.exam_payload_service import ExamPayloadService


class ExamDraftService:
    def __init__(
        self,
        exam_repository: ExamRepository,
        exam_draft_repository: ExamDraftRepository,
        exam_payload_service: ExamPayloadService,
    ) -> None:
        self._exam_repository = exam_repository
        self._exam_draft_repository = exam_draft_repository
        self._exam_payload_service = exam_payload_service

    def save(self, exam_id: int, payload: ExamDraftUpdate, current_user: User) -> dict[str, Any]:
        exam = self._exam_repository.get(exam_id)
        if not exam:
            raise NotFoundError("Exame não encontrado.")

        notes = (payload.notes or "").strip() or None
        draft = self._exam_draft_repository.get_for_exam_and_reviewer(exam.id, current_user.id)

        if draft and notes is None:
            self._exam_draft_repository.delete(draft)
        elif draft:
            draft.notes = notes
            draft.updated_at = datetime.now(UTC)
            self._exam_draft_repository.save(draft)
        elif notes is not None:
            self._exam_draft_repository.add(
                ExamDraft(exam_id=exam.id, reviewer_id=current_user.id, notes=notes)
            )

        self._exam_repository.commit()
        self._exam_repository.refresh(exam)
        return self._exam_payload_service.build(exam, include_details=True, current_user=current_user)
