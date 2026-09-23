from __future__ import annotations

from app.services.diagnosis_options_service import DiagnosisOptionsService


def _service(fake_metadata_repository, diagnosis_standardizer, null_cache_client):
    return DiagnosisOptionsService(fake_metadata_repository, diagnosis_standardizer, null_cache_client, 300)


def test_load_diagnosis_options_combines_groupings_and_metadata_conclusions(
    fake_config_repository, fake_metadata_repository, diagnosis_standardizer, null_cache_client
):
    fake_config_repository._data["diagnosis_groupings.json"] = [
        {"standard_text": "Infarto", "original_texts": []}
    ]
    fake_metadata_repository._records = [
        {"conclusions_flag": True, "conclusions": "Ritmo sinusal\nInfarto"},
        {"conclusions_flag": False, "conclusions": "Ignorado"},
    ]

    options = _service(
        fake_metadata_repository, diagnosis_standardizer, null_cache_client
    ).load_diagnosis_options()

    assert options == ["Infarto", "Ritmo sinusal"]


def test_load_diagnosis_options_dedupes_normalized_text(
    fake_config_repository, fake_metadata_repository, diagnosis_standardizer, null_cache_client
):
    fake_config_repository._data["diagnosis_groupings.json"] = [
        {"standard_text": "Infarto", "original_texts": []}
    ]
    fake_metadata_repository._records = [{"conclusions_flag": True, "conclusions": "infarto"}]

    options = _service(
        fake_metadata_repository, diagnosis_standardizer, null_cache_client
    ).load_diagnosis_options()

    assert options == ["Infarto"]


def test_load_diagnosis_options_uses_cache_when_present(diagnosis_standardizer, fake_metadata_repository):
    class RecordingCache:
        def __init__(self):
            self.store = {"diagnosis_options:v1": ["Cached"]}

        def get(self, key):
            return self.store.get(key)

        def set(self, key, value, ttl_seconds):
            raise AssertionError("should not recompute when cache hit")

    service = DiagnosisOptionsService(fake_metadata_repository, diagnosis_standardizer, RecordingCache(), 300)

    assert service.load_diagnosis_options() == ["Cached"]
