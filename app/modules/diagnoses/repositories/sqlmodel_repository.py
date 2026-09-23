from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import desc
from sqlmodel import Session, select

from app.modules.diagnoses.models import Diagnosis, DiagnosisRegion, DiagnosisValidation
from app.modules.diagnoses.repositories.interfaces import (
    DiagnosisRegionRepository,
    DiagnosisRepository,
    DiagnosisValidationRepository,
)
from app.shared.repository import SqlModelRepository


class SqlModelDiagnosisRepository(SqlModelRepository[Diagnosis], DiagnosisRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Diagnosis)

    def list_for_exam(self, exam_id: int) -> list[Diagnosis]:
        return list(
            self._session.exec(
                select(Diagnosis).where(Diagnosis.exam_id == exam_id).order_by(Diagnosis.created_at)
            ).all()
        )

    def list_original_for_exam(self, exam_id: int) -> list[Diagnosis]:
        return list(
            self._session.exec(
                select(Diagnosis)
                .where(Diagnosis.exam_id == exam_id)
                .where(Diagnosis.source == "original")
                .order_by(Diagnosis.created_at)
            ).all()
        )

    def list_for_exams(self, exam_ids: Iterable[int]) -> list[Diagnosis]:
        return list(self._session.exec(select(Diagnosis).where(Diagnosis.exam_id.in_(exam_ids))).all())


class SqlModelDiagnosisRegionRepository(SqlModelRepository[DiagnosisRegion], DiagnosisRegionRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session, DiagnosisRegion)

    def list_for_diagnosis(self, diagnosis_id: int) -> list[DiagnosisRegion]:
        return list(
            self._session.exec(
                select(DiagnosisRegion)
                .where(DiagnosisRegion.diagnosis_id == diagnosis_id)
                .order_by(DiagnosisRegion.created_at, DiagnosisRegion.id)
            ).all()
        )

    def list_for_exams(self, exam_ids: Iterable[int]) -> list[DiagnosisRegion]:
        return list(
            self._session.exec(select(DiagnosisRegion).where(DiagnosisRegion.exam_id.in_(exam_ids))).all()
        )


class SqlModelDiagnosisValidationRepository(
    SqlModelRepository[DiagnosisValidation], DiagnosisValidationRepository
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, DiagnosisValidation)

    def list_for_exam_and_cycle(self, exam_id: int, cycle_key: str) -> list[DiagnosisValidation]:
        return list(
            self._session.exec(
                select(DiagnosisValidation)
                .where(DiagnosisValidation.exam_id == exam_id)
                .where(DiagnosisValidation.cycle_key == cycle_key)
                .order_by(desc(DiagnosisValidation.updated_at))
            ).all()
        )

    def list_for_exams(self, exam_ids: Iterable[int]) -> list[DiagnosisValidation]:
        return list(
            self._session.exec(
                select(DiagnosisValidation).where(DiagnosisValidation.exam_id.in_(exam_ids))
            ).all()
        )
