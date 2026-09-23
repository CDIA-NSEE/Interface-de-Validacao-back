from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.core.settings import Settings
from app.repositories.interfaces.config_repository import ConfigRepository
from app.services.diagnosis_standardizer import DiagnosisStandardizer

ALL_EXAMS_CODE = "*"


@dataclass(frozen=True)
class ValidationContext:
    cycle_key: str
    cycle_label: str
    day_index: int | None
    general_review_day: int
    is_general_review_day: bool
    active_standard_diagnosis: str | None
    is_configured: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycle_key": self.cycle_key,
            "cycle_label": self.cycle_label,
            "day_index": self.day_index,
            "general_review_day": self.general_review_day,
            "is_general_review_day": self.is_general_review_day,
            "active_standard_diagnosis": self.active_standard_diagnosis,
            "is_configured": self.is_configured,
        }


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


class ValidationContextService:
    def __init__(
        self,
        config_repository: ConfigRepository,
        settings: Settings,
        diagnosis_standardizer: DiagnosisStandardizer,
    ) -> None:
        self._config_repository = config_repository
        self._settings = settings
        self._diagnosis_standardizer = diagnosis_standardizer

    def load_validation_calendar(self) -> dict:
        data = self._config_repository.load_json(
            "validation_calendar.json",
            {
                "cycle_key": "default",
                "cycle_label": "Ciclo de validacao ECG",
                "cycle_start_date": None,
                "active_day_index": None,
                "general_review_day": 30,
                "days": [],
            },
        )

        return {
            "cycle_key": str(data.get("cycle_key") or "default"),
            "cycle_label": str(data.get("cycle_label") or "Ciclo de validacao ECG"),
            "cycle_start_date": data.get("cycle_start_date"),
            "active_day_index": data.get("active_day_index"),
            "general_review_day": int(data.get("general_review_day") or 30),
            "days": list(data.get("days") or []),
        }

    def active_context(self, today: date | None = None) -> ValidationContext:
        today = today or date.today()
        calendar = self.load_validation_calendar()
        general_review_day = calendar["general_review_day"]
        validation_settings = self._settings.validation
        day_index = _coerce_int(validation_settings.cycle_day)

        if day_index is None:
            day_index = _coerce_int(calendar.get("active_day_index"))

        if day_index is None:
            start_date = _parse_date(calendar.get("cycle_start_date"))
            if start_date:
                day_index = ((today - start_date).days % general_review_day) + 1

        env_diagnosis = validation_settings.active_diagnosis
        active_standard_diagnosis = env_diagnosis.strip() if env_diagnosis else None

        if day_index is not None and not active_standard_diagnosis:
            for day in calendar["days"]:
                if _coerce_int(day.get("day_index")) == day_index:
                    active_standard_diagnosis = str(day.get("standard_diagnosis") or "").strip() or None
                    break

        is_general_review_day = day_index == general_review_day
        is_configured = bool(is_general_review_day or active_standard_diagnosis)

        return ValidationContext(
            cycle_key=calendar["cycle_key"],
            cycle_label=calendar["cycle_label"],
            day_index=day_index,
            general_review_day=general_review_day,
            is_general_review_day=is_general_review_day,
            active_standard_diagnosis=active_standard_diagnosis,
            is_configured=is_configured,
        )

    @staticmethod
    def _parse_boolean_override(value: str) -> bool | None:
        normalized_value = value.strip().lower()
        if normalized_value in {"1", "true", "yes", "on"}:
            return True
        if normalized_value in {"0", "false", "no", "off"}:
            return False
        return None

    def load_ai_recommendations(self) -> dict:
        disabled_config = {"enabled": False, "suggestions": []}
        try:
            data = self._config_repository.load_json("ai_recommendations.json", None)
        except (OSError, ValueError, TypeError):
            return disabled_config

        if (
            not isinstance(data, dict)
            or not isinstance(data.get("enabled"), bool)
            or not isinstance(data.get("suggestions"), list)
        ):
            return disabled_config

        enabled = data["enabled"]
        env_override = self._settings.validation.ai_mode_enabled
        if env_override is not None:
            parsed_override = self._parse_boolean_override(env_override)
            if parsed_override is None:
                return disabled_config
            enabled = parsed_override

        if not enabled:
            return disabled_config

        suggestions = []
        for entry in data["suggestions"]:
            if not isinstance(entry, dict):
                continue

            raw_exam_code = entry.get("exam_code")
            diagnosis_values = entry.get("standard_diagnoses")
            if not isinstance(raw_exam_code, str) or not isinstance(diagnosis_values, list):
                continue
            exam_code = raw_exam_code.strip()
            if not exam_code:
                continue

            standard_diagnoses = []
            normalized_diagnoses = set()
            for diagnosis in diagnosis_values:
                if not isinstance(diagnosis, str):
                    continue
                standard_text = self._diagnosis_standardizer.standardize(diagnosis.strip())
                normalized_standard_text = self._diagnosis_standardizer.normalize_text(standard_text)
                if not normalized_standard_text or normalized_standard_text in normalized_diagnoses:
                    continue
                normalized_diagnoses.add(normalized_standard_text)
                standard_diagnoses.append(standard_text)

            if standard_diagnoses:
                suggestions.append({"exam_code": exam_code, "standard_diagnoses": standard_diagnoses})

        return {"enabled": enabled, "suggestions": suggestions}

    def ai_suggested(
        self,
        exam_code: str | None,
        diagnosis_text: str | None,
        recommendations: dict | None = None,
    ) -> bool:
        if recommendations is None:
            recommendations = self.load_ai_recommendations()
        if not recommendations.get("enabled"):
            return False

        normalized_exam_code = self._diagnosis_standardizer.normalize_text(exam_code)
        normalized_diagnosis = self._diagnosis_standardizer.normalize_text(
            self._diagnosis_standardizer.standardize(diagnosis_text)
        )
        if not normalized_exam_code or not normalized_diagnosis:
            return False

        for suggestion in recommendations.get("suggestions", []):
            if not isinstance(suggestion, dict):
                continue
            configured_exam_code = self._diagnosis_standardizer.normalize_text(suggestion.get("exam_code"))
            if configured_exam_code != ALL_EXAMS_CODE and configured_exam_code != normalized_exam_code:
                continue
            standard_diagnoses = suggestion.get("standard_diagnoses", [])
            if not isinstance(standard_diagnoses, list):
                continue
            if any(
                self._diagnosis_standardizer.normalize_text(item) == normalized_diagnosis
                for item in standard_diagnoses
                if isinstance(item, str)
            ):
                return True

        return False

    def load_support_contact(self) -> dict:
        data = self._config_repository.load_json(
            "support_contact.json",
            {
                "title": "Contato BP/NSEE",
                "description": "Canais oficiais de suporte ainda pendentes de configuracao.",
                "channels": [],
            },
        )

        support_settings = self._settings.support
        env_label = support_settings.label
        env_value = support_settings.value
        if env_label and env_value:
            data["channels"] = [
                {
                    "label": env_label.strip(),
                    "type": (support_settings.type or "text").strip() or "text",
                    "value": env_value.strip(),
                }
            ]

        data["channels"] = [
            {
                "label": str(channel.get("label", "")).strip(),
                "type": str(channel.get("type", "text")).strip() or "text",
                "value": str(channel.get("value", "")).strip(),
            }
            for channel in data.get("channels", [])
            if str(channel.get("label", "")).strip() and str(channel.get("value", "")).strip()
        ]
        return data

    def context_payload(self) -> dict:
        context = self.active_context()
        ai_recommendations = self.load_ai_recommendations()
        return {
            **context.as_dict(),
            "ai_mode_enabled": ai_recommendations["enabled"],
            "support_contact": self.load_support_contact(),
        }
