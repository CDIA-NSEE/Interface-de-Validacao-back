from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.services.diagnosis_deleter import DiagnosisDeleter
from tests.unit.services.conftest import make_diagnosis, make_exam


@pytest.fixture()
def deleter(diagnosis_repository, diagnosis_region_repository, exam_repository):
    return DiagnosisDeleter(diagnosis_repository, diagnosis_region_repository, exam_repository)


def test_delete_raises_not_found_for_missing_exam(session, deleter):
    with pytest.raises(NotFoundError):
        deleter.delete(999, 1)


def test_delete_raises_not_found_when_diagnosis_belongs_to_other_exam(session, deleter):
    exam = make_exam(session)
    other_exam = make_exam(session)
    diagnosis = make_diagnosis(session, other_exam)

    with pytest.raises(NotFoundError):
        deleter.delete(exam.id, diagnosis.id)


def test_delete_blocks_removing_original_diagnosis(session, deleter):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, source="original")

    with pytest.raises(ValidationError):
        deleter.delete(exam.id, diagnosis.id)


def test_delete_removes_doctor_added_diagnosis(session, deleter, diagnosis_repository):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, source="doctor_added")

    deleted_id = deleter.delete(exam.id, diagnosis.id)

    assert deleted_id == diagnosis.id
    assert diagnosis_repository.get(diagnosis.id) is None
