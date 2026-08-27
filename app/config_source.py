from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any


CONFIG_DIR = Path(__file__).resolve().parent / "config"
GENERAL_REVIEW_STANDARD_TEXT = "__GENERAL_REVIEW__"
ALL_EXAMS_CODE = "*"


def _load_json(name: str, default: Any) -> Any:
    path = CONFIG_DIR / name
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _split_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    decomposed = unicodedata.normalize("NFD", value)
    ascii_text = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", ascii_text.upper()).strip()


def load_auth_config() -> dict:
    data = _load_json("auth_config.json", {"allowed_email_domains": []})
    return {
        "allowed_email_domains": [
            domain.strip().lower()
            for domain in data.get("allowed_email_domains", [])
            if str(domain).strip()
        ]
    }


def allowed_email_domains() -> list[str]:
    env_domains = os.getenv("BP_ALLOWED_EMAIL_DOMAINS")
    if env_domains is not None:
        return _split_csv(env_domains)
    return load_auth_config()["allowed_email_domains"]


def email_domain_allowed(identifier: str) -> bool:
    domains = allowed_email_domains()
    if not domains:
        return True

    if "@" not in identifier:
        return False

    domain = identifier.rsplit("@", 1)[1].strip().lower()
    return domain in domains


def load_diagnosis_groupings() -> list[dict]:
    groups = _load_json("diagnosis_groupings.json", [])
    normalized_groups = []

    for group in groups:
        standard_text = str(group.get("standard_text", "")).strip()
        if not standard_text:
            continue

        original_texts = [
            str(item).strip()
            for item in group.get("original_texts", [])
            if str(item).strip()
        ]
        normalized_groups.append(
            {
                "standard_text": standard_text,
                "original_texts": original_texts,
                "normalized_standard_text": normalize_text(standard_text),
                "normalized_original_texts": {normalize_text(item) for item in original_texts},
            }
        )

    return normalized_groups


def standardize_diagnosis(original_text: str | None) -> str:
    normalized_text = normalize_text(original_text)
    if not normalized_text:
        return ""

    for group in load_diagnosis_groupings():
        if normalized_text == group["normalized_standard_text"]:
            return group["standard_text"]
        if normalized_text in group["normalized_original_texts"]:
            return group["standard_text"]

    return str(original_text or "").strip()


def _parse_boolean_override(value: str) -> bool | None:
    normalized_value = value.strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    return None


def load_ai_recommendations() -> dict:
    disabled_config = {"enabled": False, "suggestions": []}
    try:
        data = _load_json("ai_recommendations.json", None)
    except (OSError, ValueError, TypeError):
        return disabled_config

    if (
        not isinstance(data, dict)
        or not isinstance(data.get("enabled"), bool)
        or not isinstance(data.get("suggestions"), list)
    ):
        return disabled_config

    enabled = data["enabled"]
    env_override = os.getenv("AI_MODE_ENABLED")
    if env_override is not None:
        parsed_override = _parse_boolean_override(env_override)
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
            standard_text = standardize_diagnosis(diagnosis.strip())
            normalized_standard_text = normalize_text(standard_text)
            if not normalized_standard_text or normalized_standard_text in normalized_diagnoses:
                continue
            normalized_diagnoses.add(normalized_standard_text)
            standard_diagnoses.append(standard_text)

        if standard_diagnoses:
            suggestions.append(
                {
                    "exam_code": exam_code,
                    "standard_diagnoses": standard_diagnoses,
                }
            )

    return {"enabled": enabled, "suggestions": suggestions}


def ai_suggested(
    exam_code: str | None,
    diagnosis_text: str | None,
    recommendations: dict | None = None,
) -> bool:
    if recommendations is None:
        recommendations = load_ai_recommendations()
    if not recommendations.get("enabled"):
        return False

    normalized_exam_code = normalize_text(exam_code)
    normalized_diagnosis = normalize_text(standardize_diagnosis(diagnosis_text))
    if not normalized_exam_code or not normalized_diagnosis:
        return False

    for suggestion in recommendations.get("suggestions", []):
        if not isinstance(suggestion, dict):
            continue
        configured_exam_code = normalize_text(suggestion.get("exam_code"))
        if (
            configured_exam_code != ALL_EXAMS_CODE
            and configured_exam_code != normalized_exam_code
        ):
            continue
        standard_diagnoses = suggestion.get("standard_diagnoses", [])
        if not isinstance(standard_diagnoses, list):
            continue
        if any(
            normalize_text(item) == normalized_diagnosis
            for item in standard_diagnoses
            if isinstance(item, str)
        ):
            return True

    return False


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_validation_calendar() -> dict:
    data = _load_json(
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


def active_validation_context(today: date | None = None) -> dict:
    today = today or date.today()
    calendar = load_validation_calendar()
    general_review_day = calendar["general_review_day"]
    day_index = _coerce_int(os.getenv("VALIDATION_CYCLE_DAY"))

    if day_index is None:
        day_index = _coerce_int(calendar.get("active_day_index"))

    if day_index is None:
        start_date = _parse_date(calendar.get("cycle_start_date"))
        if start_date:
            day_index = ((today - start_date).days % general_review_day) + 1

    env_diagnosis = os.getenv("VALIDATION_ACTIVE_DIAGNOSIS")
    active_standard_diagnosis = env_diagnosis.strip() if env_diagnosis else None

    if day_index is not None and not active_standard_diagnosis:
        for day in calendar["days"]:
            if _coerce_int(day.get("day_index")) == day_index:
                active_standard_diagnosis = str(day.get("standard_diagnosis") or "").strip() or None
                break

    is_general_review_day = day_index == general_review_day
    is_configured = bool(is_general_review_day or active_standard_diagnosis)

    return {
        "cycle_key": calendar["cycle_key"],
        "cycle_label": calendar["cycle_label"],
        "day_index": day_index,
        "general_review_day": general_review_day,
        "is_general_review_day": is_general_review_day,
        "active_standard_diagnosis": active_standard_diagnosis,
        "is_configured": is_configured,
    }


def load_support_contact() -> dict:
    data = _load_json(
        "support_contact.json",
        {
            "title": "Contato BP/NSEE",
            "description": "Canais oficiais de suporte ainda pendentes de configuracao.",
            "channels": [],
        },
    )

    env_label = os.getenv("SUPPORT_CONTACT_LABEL")
    env_value = os.getenv("SUPPORT_CONTACT_VALUE")
    if env_label and env_value:
        data["channels"] = [
            {
                "label": env_label.strip(),
                "type": os.getenv("SUPPORT_CONTACT_TYPE", "text").strip() or "text",
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
