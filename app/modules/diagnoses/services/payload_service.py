from __future__ import annotations

from typing import Any

from app.core.exceptions import ValidationError
from app.modules.diagnoses.models import Diagnosis, DiagnosisRegion, DiagnosisValidation
from app.modules.diagnoses.repositories.interfaces import (
    DiagnosisRegionRepository,
    DiagnosisValidationRepository,
)
from app.modules.diagnoses.services.standardizer import DiagnosisStandardizer
from app.modules.validation.services.context_service import ValidationContext, ValidationContextService


class DiagnosisPayloadService:
    def __init__(
        self,
        diagnosis_region_repository: DiagnosisRegionRepository,
        diagnosis_validation_repository: DiagnosisValidationRepository,
        diagnosis_standardizer: DiagnosisStandardizer,
        validation_context_service: ValidationContextService,
    ) -> None:
        self._diagnosis_region_repository = diagnosis_region_repository
        self._diagnosis_validation_repository = diagnosis_validation_repository
        self._diagnosis_standardizer = diagnosis_standardizer
        self._validation_context_service = validation_context_service

    @staticmethod
    def _legacy_region_payload(diagnosis: Diagnosis) -> dict | None:
        if diagnosis.region_width and diagnosis.region_height:
            return {
                "id": None,
                "x": diagnosis.region_x,
                "y": diagnosis.region_y,
                "width": diagnosis.region_width,
                "height": diagnosis.region_height,
                "created_at": diagnosis.created_at,
                "legacy": True,
            }
        return None

    @staticmethod
    def _region_payload(region: DiagnosisRegion) -> dict:
        return {
            "id": region.id,
            "x": region.x,
            "y": region.y,
            "width": region.width,
            "height": region.height,
            "created_at": region.created_at,
            "legacy": False,
        }

    def diagnosis_region_payloads(self, diagnosis: Diagnosis) -> list[dict]:
        regions = [
            self._region_payload(region)
            for region in self._diagnosis_region_repository.list_for_diagnosis(diagnosis.id)
        ]
        if regions:
            return regions

        legacy_region = self._legacy_region_payload(diagnosis)
        return [legacy_region] if legacy_region else []

    def latest_standard_validation(
        self, exam_id: int, standard_text: str, cycle_key: str
    ) -> DiagnosisValidation | None:
        validations = self._diagnosis_validation_repository.list_for_exam_and_cycle(exam_id, cycle_key)
        normalized_standard_text = self._diagnosis_standardizer.normalize_text(standard_text)
        return next(
            (
                validation
                for validation in validations
                if self._diagnosis_standardizer.normalize_text(validation.standard_text)
                == normalized_standard_text
            ),
            None,
        )

    def effective_review_status(self, diagnosis: Diagnosis, context: ValidationContext | None = None) -> str:
        context = context or self._validation_context_service.active_context()
        standard_text = self._diagnosis_standardizer.standardize(diagnosis.name)
        validation = self.latest_standard_validation(diagnosis.exam_id, standard_text, context.cycle_key)
        return validation.review_status if validation else diagnosis.review_status

    def ensure_region_before_confirm(self, diagnosis: Diagnosis) -> None:
        standard_text = self._diagnosis_standardizer.standardize(diagnosis.name)
        regions = self.diagnosis_region_payloads(diagnosis)
        if self._diagnosis_standardizer.requires_region(standard_text, diagnosis.name) and not regions:
            raise ValidationError(
                "Marque ao menos uma area do ECG antes de confirmar um diagnostico de infarto."
            )

    def build(
        self,
        diagnosis: Diagnosis,
        context: ValidationContext | None = None,
        exam_code: str | None = None,
        ai_recommendations: dict | None = None,
    ) -> dict[str, Any]:
        context = context or self._validation_context_service.active_context()
        recommendations = (
            ai_recommendations
            if ai_recommendations is not None
            else self._validation_context_service.load_ai_recommendations()
        )
        standard_text = self._diagnosis_standardizer.standardize(diagnosis.name)
        is_grouped = not self._diagnosis_standardizer.same_standard_text(standard_text, diagnosis.name)
        regions = self.diagnosis_region_payloads(diagnosis)
        requires_region = self._diagnosis_standardizer.requires_region(standard_text, diagnosis.name)
        validation = self.latest_standard_validation(diagnosis.exam_id, standard_text, context.cycle_key)
        active_standard_diagnosis = context.active_standard_diagnosis
        validation_status = validation.review_status if validation else diagnosis.review_status

        return {
            "id": diagnosis.id,
            "exam_id": diagnosis.exam_id,
            "name": diagnosis.name,
            "standard_text": standard_text,
            "original_text": diagnosis.name,
            "is_grouped": is_grouped,
            "regions": regions,
            "regions_count": len(regions),
            "requires_region": requires_region,
            "region_required_missing": bool(requires_region and not regions),
            "source": diagnosis.source,
            "review_status": validation_status,
            "legacy_review_status": diagnosis.review_status,
            "validation_status": validation_status,
            "validation_id": validation.id if validation else None,
            "validated_at": validation.updated_at if validation else None,
            "review_notes": validation.notes if validation and validation.notes else None,
            "daily_required": bool(
                diagnosis.source == "original"
                and active_standard_diagnosis
                and self._diagnosis_standardizer.same_standard_text(standard_text, active_standard_diagnosis)
            ),
            "ai_suggested": self._validation_context_service.ai_suggested(
                exam_code, standard_text, recommendations
            ),
            "is_abnormal": diagnosis.is_abnormal,
            "region_x": diagnosis.region_x,
            "region_y": diagnosis.region_y,
            "region_width": diagnosis.region_width,
            "region_height": diagnosis.region_height,
            "created_at": diagnosis.created_at,
        }
