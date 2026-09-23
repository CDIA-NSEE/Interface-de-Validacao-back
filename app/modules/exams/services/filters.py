from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import ValidationError

VALID_STATUSES = {"nao_validado", "em_validacao", "valido"}
VALID_REVIEW_RESULTS = {"sem_alteracao", "alterado"}
VALID_QUEUE_STATES = {"all", "start", "validated", "completed"}
VALID_DECISION_FILTERS = {"confirmed", "rejected"}
VALID_REGION_FILTERS = {"with_region", "without_region"}
VALID_SOURCE_FILTERS = {"pending", "reviewed", "all"}


def validate_status(status_validation: str) -> None:
    if status_validation not in VALID_STATUSES:
        raise ValidationError("status_validation inválido.")


@dataclass(frozen=True)
class ExamListFilters:
    status: str | None = None
    category: str | None = None
    exam_type: str | None = None
    source: str | None = None
    review_result: str | None = None
    queue_state: str | None = None
    decision: str | None = None
    region: str | None = None
    search: str | None = None

    def validate(self) -> None:
        if self.status:
            validate_status(self.status)
        if self.review_result and self.review_result not in VALID_REVIEW_RESULTS:
            raise ValidationError("review_result inválido.")
        if self.source and self.source not in VALID_SOURCE_FILTERS:
            raise ValidationError("source deve ser pending, reviewed ou all.")
        if self.queue_state and self.queue_state not in VALID_QUEUE_STATES:
            raise ValidationError("queue_state invalido.")
        if self.decision and self.decision not in VALID_DECISION_FILTERS:
            raise ValidationError("decision deve ser confirmed ou rejected.")
        if self.region and self.region not in VALID_REGION_FILTERS:
            raise ValidationError("region deve ser with_region ou without_region.")
