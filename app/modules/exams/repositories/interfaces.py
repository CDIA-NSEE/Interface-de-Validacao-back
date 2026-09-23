from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable

from app.modules.exams.models import Exam, ExamDraft, Review
from app.shared.repository import Repository


class ExamRepository(Repository[Exam, int]):
    @abstractmethod
    def list_all(self) -> list[Exam]: ...

    @abstractmethod
    def first(self) -> Exam | None: ...

    @abstractmethod
    def list_recent(self) -> list[Exam]:
        """Ordered by exam_date desc, created_at desc."""

    @abstractmethod
    def list_by_codes(self, exam_codes: Iterable[str]) -> list[Exam]: ...

    @abstractmethod
    def first_for_patient(self, patient_id: int) -> Exam | None: ...

    @abstractmethod
    def list_imported_metadata_hashes(self) -> set[str]: ...


class ExamDraftRepository(Repository[ExamDraft, int]):
    @abstractmethod
    def get_for_exam_and_reviewer(self, exam_id: int, reviewer_id: int) -> ExamDraft | None: ...

    @abstractmethod
    def list_for_exams(self, exam_ids: Iterable[int]) -> list[ExamDraft]: ...


class ReviewRepository(Repository[Review, int]):
    @abstractmethod
    def list_for_exam(self, exam_id: int) -> list[Review]:
        """Ordered by created_at."""

    @abstractmethod
    def list_completed(self) -> list[Review]:
        """status_after == 'valido'."""

    @abstractmethod
    def list_for_exams(self, exam_ids: Iterable[int]) -> list[Review]: ...
