from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import desc
from sqlmodel import Session, select

from app.modules.exams.models import Exam, ExamDraft, Review
from app.modules.exams.repositories.interfaces import (
    ExamDraftRepository,
    ExamRepository,
    ReviewRepository,
)
from app.shared.repository import SqlModelRepository


class SqlModelExamRepository(SqlModelRepository[Exam], ExamRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Exam)

    def list_all(self) -> list[Exam]:
        return list(self._session.exec(select(Exam)).all())

    def first(self) -> Exam | None:
        return self._session.exec(select(Exam)).first()

    def list_recent(self) -> list[Exam]:
        return list(
            self._session.exec(select(Exam).order_by(desc(Exam.exam_date), desc(Exam.created_at))).all()
        )

    def list_by_codes(self, exam_codes: Iterable[str]) -> list[Exam]:
        return list(self._session.exec(select(Exam).where(Exam.exam_code.in_(exam_codes))).all())

    def first_for_patient(self, patient_id: int) -> Exam | None:
        return self._session.exec(select(Exam).where(Exam.patient_id == patient_id)).first()

    def list_imported_metadata_hashes(self) -> set[str]:
        return {
            metadata_hash
            for metadata_hash in self._session.exec(select(Exam.metadata_hash)).all()
            if metadata_hash
        }


class SqlModelExamDraftRepository(SqlModelRepository[ExamDraft], ExamDraftRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ExamDraft)

    def get_for_exam_and_reviewer(self, exam_id: int, reviewer_id: int) -> ExamDraft | None:
        return self._session.exec(
            select(ExamDraft).where(ExamDraft.exam_id == exam_id).where(ExamDraft.reviewer_id == reviewer_id)
        ).first()

    def list_for_exams(self, exam_ids: Iterable[int]) -> list[ExamDraft]:
        return list(self._session.exec(select(ExamDraft).where(ExamDraft.exam_id.in_(exam_ids))).all())


class SqlModelReviewRepository(SqlModelRepository[Review], ReviewRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Review)

    def list_for_exam(self, exam_id: int) -> list[Review]:
        return list(
            self._session.exec(
                select(Review).where(Review.exam_id == exam_id).order_by(Review.created_at)
            ).all()
        )

    def list_completed(self) -> list[Review]:
        return list(self._session.exec(select(Review).where(Review.status_after == "valido")).all())

    def list_for_exams(self, exam_ids: Iterable[int]) -> list[Review]:
        return list(self._session.exec(select(Review).where(Review.exam_id.in_(exam_ids))).all())
