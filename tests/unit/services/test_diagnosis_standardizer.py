from __future__ import annotations

from app.services.diagnosis_standardizer import DiagnosisStandardizer


def test_normalize_text_strips_accents_and_uppercases():
    assert DiagnosisStandardizer.normalize_text("  infarto agudo  ") == "INFARTO AGUDO"
    assert DiagnosisStandardizer.normalize_text("São Paulo") == "SAO PAULO"
    assert DiagnosisStandardizer.normalize_text(None) == ""


def test_load_diagnosis_groupings_normalizes_entries(fake_config_repository):
    fake_config_repository._data["diagnosis_groupings.json"] = [
        {
            "standard_text": "Infarto",
            "original_texts": [" infarto agudo ", "IAM"],
        }
    ]
    standardizer = DiagnosisStandardizer(fake_config_repository)

    groups = standardizer.load_diagnosis_groupings()

    assert groups[0]["standard_text"] == "Infarto"
    assert "INFARTO AGUDO" in groups[0]["normalized_original_texts"]
    assert "IAM" in groups[0]["normalized_original_texts"]


def test_standardize_returns_matching_group_standard_text(fake_config_repository):
    fake_config_repository._data["diagnosis_groupings.json"] = [
        {"standard_text": "Infarto", "original_texts": ["infarto agudo"]}
    ]
    standardizer = DiagnosisStandardizer(fake_config_repository)

    assert standardizer.standardize("Infarto Agudo") == "Infarto"
    assert standardizer.standardize("Ritmo sinusal") == "Ritmo sinusal"
    assert standardizer.standardize(None) == ""


def test_same_standard_text_compares_normalized(fake_config_repository):
    standardizer = DiagnosisStandardizer(fake_config_repository)
    assert standardizer.same_standard_text("Infarto", "infarto") is True
    assert standardizer.same_standard_text("Infarto", "Outro") is False


def test_requires_region_detects_infarto_and_iam_token():
    assert DiagnosisStandardizer.requires_region("Infarto do miocardio", "Infarto do miocardio") is True
    assert DiagnosisStandardizer.requires_region("IAM anterior", "IAM anterior") is True
    assert DiagnosisStandardizer.requires_region("Ritmo sinusal", "Ritmo sinusal") is False
