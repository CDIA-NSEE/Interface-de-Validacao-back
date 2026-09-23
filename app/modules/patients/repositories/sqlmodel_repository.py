from __future__ import annotations

from sqlmodel import Session

from app.modules.patients.models import Patient
from app.modules.patients.repositories.interfaces import PatientRepository
from app.shared.repository import SqlModelRepository


class SqlModelPatientRepository(SqlModelRepository[Patient], PatientRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Patient)
