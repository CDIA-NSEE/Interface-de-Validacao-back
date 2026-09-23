from __future__ import annotations

import re
import unicodedata

from app.shared.config.interfaces import ConfigRepository


class DiagnosisStandardizer:
    def __init__(self, config_repository: ConfigRepository) -> None:
        self._config_repository = config_repository

    @staticmethod
    def normalize_text(value: str | None) -> str:
        if not value:
            return ""

        decomposed = unicodedata.normalize("NFD", value)
        ascii_text = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
        return re.sub(r"\s+", " ", ascii_text.upper()).strip()

    def load_diagnosis_groupings(self) -> list[dict]:
        groups = self._config_repository.load_json("diagnosis_groupings.json", [])
        normalized_groups = []

        for group in groups:
            standard_text = str(group.get("standard_text", "")).strip()
            if not standard_text:
                continue

            original_texts = [
                str(item).strip() for item in group.get("original_texts", []) if str(item).strip()
            ]
            normalized_groups.append(
                {
                    "standard_text": standard_text,
                    "original_texts": original_texts,
                    "normalized_standard_text": self.normalize_text(standard_text),
                    "normalized_original_texts": {self.normalize_text(item) for item in original_texts},
                }
            )

        return normalized_groups

    def standardize(self, original_text: str | None) -> str:
        normalized_text = self.normalize_text(original_text)
        if not normalized_text:
            return ""

        for group in self.load_diagnosis_groupings():
            if normalized_text == group["normalized_standard_text"]:
                return group["standard_text"]
            if normalized_text in group["normalized_original_texts"]:
                return group["standard_text"]

        return str(original_text or "").strip()

    def same_standard_text(self, left: str | None, right: str | None) -> bool:
        return self.normalize_text(left) == self.normalize_text(right)

    @staticmethod
    def requires_region(standard_text: str | None, original_text: str | None) -> bool:
        normalized_values = [
            DiagnosisStandardizer.normalize_text(standard_text),
            DiagnosisStandardizer.normalize_text(original_text),
        ]
        for normalized_text in normalized_values:
            if "INFARTO" in normalized_text:
                return True

            tokens = re.findall(r"[A-Z0-9]+", normalized_text)
            if any(token == "IAM" or token.startswith("IAM") for token in tokens):
                return True

        return False
