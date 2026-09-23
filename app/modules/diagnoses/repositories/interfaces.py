from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable

from app.modules.diagnoses.models import Diagnosis, DiagnosisRegion, DiagnosisValidation
from app.shared.repository import Repository


class DiagnosisRepository(Repository[Diagnosis, int]):
    @abstractmethod
    def list_for_exam(self, exam_id: int) -> list[Diagnosis]:
        """Ordered by created_at."""

    @abstractmethod
    def list_original_for_exam(self, exam_id: int) -> list[Diagnosis]:
        """source == 'original', ordered by created_at."""

    @abstractmethod
    def list_for_exams(self, exam_ids: Iterable[int]) -> list[Diagnosis]: ...


class DiagnosisRegionRepository(Repository[DiagnosisRegion, int]):
    @abstractmethod
    def list_for_diagnosis(self, diagnosis_id: int) -> list[DiagnosisRegion]:
        """Ordered by created_at, id."""

    @abstractmethod
    def list_for_exams(self, exam_ids: Iterable[int]) -> list[DiagnosisRegion]: ...


class DiagnosisValidationRepository(Repository[DiagnosisValidation, int]):
    @abstractmethod
    def list_for_exam_and_cycle(self, exam_id: int, cycle_key: str) -> list[DiagnosisValidation]:
        """Ordered by updated_at desc."""

    @abstractmethod
    def list_for_exams(self, exam_ids: Iterable[int]) -> list[DiagnosisValidation]: ...
