from __future__ import annotations

from app.modules.patients.models import Patient
from app.shared.repository import Repository


class PatientRepository(Repository[Patient, int]):
    """No aggregate-specific queries beyond the generic CRUD shape."""
