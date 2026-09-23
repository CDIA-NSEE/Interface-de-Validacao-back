from __future__ import annotations

from app.modules.diagnoses.services.standardizer import DiagnosisStandardizer
from app.modules.metadata.interfaces import MetadataRepository
from app.shared.cache.interfaces import CacheClient

_CACHE_KEY = "diagnosis_options:v1"


class DiagnosisOptionsService:
    def __init__(
        self,
        metadata_repository: MetadataRepository,
        diagnosis_standardizer: DiagnosisStandardizer,
        cache_client: CacheClient,
        cache_ttl_seconds: int,
    ) -> None:
        self._metadata_repository = metadata_repository
        self._diagnosis_standardizer = diagnosis_standardizer
        self._cache_client = cache_client
        self._cache_ttl_seconds = cache_ttl_seconds

    @staticmethod
    def _conclusion_items(conclusions: str | None) -> list[str]:
        if not conclusions:
            return []
        return [line.strip() for line in conclusions.splitlines() if line.strip()]

    def load_diagnosis_options(self) -> list[str]:
        cached = self._cache_client.get(_CACHE_KEY)
        if cached is not None:
            return cached

        options = self._build_diagnosis_options()
        self._cache_client.set(_CACHE_KEY, options, self._cache_ttl_seconds)
        return options

    def _build_diagnosis_options(self) -> list[str]:
        options = []
        seen = set()

        for group in self._diagnosis_standardizer.load_diagnosis_groupings():
            standard_text = group["standard_text"]
            normalized_text = self._diagnosis_standardizer.normalize_text(standard_text)
            if normalized_text and normalized_text not in seen:
                options.append(standard_text)
                seen.add(normalized_text)

        for record in self._metadata_repository.load_records():
            if record["conclusions_flag"]:
                for diagnosis in self._conclusion_items(record["conclusions"]):
                    standard_text = self._diagnosis_standardizer.standardize(diagnosis)
                    normalized_text = self._diagnosis_standardizer.normalize_text(standard_text)
                    if normalized_text and normalized_text not in seen:
                        options.append(standard_text)
                        seen.add(normalized_text)

        return options
