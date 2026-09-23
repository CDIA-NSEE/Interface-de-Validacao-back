from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.services.exam_filters import ExamListFilters, validate_status


def test_validate_status_accepts_known_values():
    validate_status("nao_validado")


def test_validate_status_rejects_unknown_value():
    with pytest.raises(ValidationError):
        validate_status("bogus")


def test_exam_list_filters_validate_accepts_all_none():
    ExamListFilters().validate()


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "bogus"),
        ("review_result", "bogus"),
        ("source", "bogus"),
        ("queue_state", "bogus"),
        ("decision", "bogus"),
        ("region", "bogus"),
    ],
)
def test_exam_list_filters_validate_rejects_invalid_fields(field, value):
    filters = ExamListFilters(**{field: value})
    with pytest.raises(ValidationError):
        filters.validate()
