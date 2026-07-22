from datetime import date
import os
import unittest
from unittest.mock import MagicMock, mock_open, patch

from app import config_source


class ConfigSourceTest(unittest.TestCase):
    def test_load_json_uses_default_for_missing_file_and_reads_existing_file(self):
        config_directory = MagicMock()
        missing_path = MagicMock()
        missing_path.exists.return_value = False
        existing_path = MagicMock()
        existing_path.exists.return_value = True
        existing_path.open = mock_open(read_data='{"value": [1, 2, 3]}')
        config_directory.__truediv__.side_effect = [missing_path, existing_path]

        with patch.object(config_source, "CONFIG_DIR", config_directory):
            self.assertEqual(
                config_source._load_json("missing.json", {"default": True}),
                {"default": True},
            )
            self.assertEqual(
                config_source._load_json("existing.json", {}),
                {"value": [1, 2, 3]},
            )

    def test_csv_and_text_normalization_handle_empty_spacing_and_accents(self):
        self.assertEqual(config_source._split_csv(None), [])
        self.assertEqual(
            config_source._split_csv(" Example.COM, hospital.org, ,"),
            ["example.com", "hospital.org"],
        )
        self.assertEqual(config_source.normalize_text(None), "")
        self.assertEqual(
            config_source.normalize_text("  Altera\u00e7\u00e3o\n  card\u00edaca "),
            "ALTERACAO CARDIACA",
        )

    def test_auth_config_and_email_domain_rules(self):
        with patch.object(
            config_source,
            "_load_json",
            return_value={"allowed_email_domains": [" Example.org ", "", "123"]},
        ):
            self.assertEqual(
                config_source.load_auth_config(),
                {"allowed_email_domains": ["example.org", "123"]},
            )

        with patch.dict(os.environ, {"BP_ALLOWED_EMAIL_DOMAINS": "Example.org, hospital.org"}, clear=True):
            self.assertEqual(
                config_source.allowed_email_domains(),
                ["example.org", "hospital.org"],
            )
            self.assertTrue(config_source.email_domain_allowed("Doctor@EXAMPLE.ORG"))
            self.assertFalse(config_source.email_domain_allowed("doctor@blocked.org"))
            self.assertFalse(config_source.email_domain_allowed("not-an-email"))

        with patch.dict(os.environ, {}, clear=True), patch.object(
            config_source,
            "load_auth_config",
            return_value={"allowed_email_domains": []},
        ):
            self.assertTrue(config_source.email_domain_allowed("any-identifier"))

    def test_groupings_discard_invalid_rows_and_standardize_known_variants(self):
        data = [
            {"standard_text": "", "original_texts": ["ignored"]},
            {
                "standard_text": "Ritmo sinusal",
                "original_texts": [" RITMO  SINUSAL ", ""],
            },
        ]
        with patch.object(config_source, "_load_json", return_value=data):
            groups = config_source.load_diagnosis_groupings()

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["standard_text"], "Ritmo sinusal")
        self.assertEqual(groups[0]["original_texts"], ["RITMO  SINUSAL"])
        self.assertEqual(groups[0]["normalized_standard_text"], "RITMO SINUSAL")

        with patch.object(config_source, "load_diagnosis_groupings", return_value=groups):
            self.assertEqual(config_source.standardize_diagnosis("ritmo sinusal"), "Ritmo sinusal")
            self.assertEqual(config_source.standardize_diagnosis("Outro achado"), "Outro achado")
            self.assertEqual(config_source.standardize_diagnosis("  "), "")

    def test_date_and_integer_parsers_cover_valid_and_invalid_values(self):
        self.assertIsNone(config_source._parse_date(None))
        self.assertEqual(config_source._parse_date("2026-07-21"), date(2026, 7, 21))
        self.assertIsNone(config_source._coerce_int(None))
        self.assertIsNone(config_source._coerce_int(""))
        self.assertIsNone(config_source._coerce_int("invalid"))
        self.assertEqual(config_source._coerce_int("12"), 12)

    def test_validation_calendar_applies_defaults_and_coerces_collections(self):
        with patch.object(
            config_source,
            "_load_json",
            return_value={
                "cycle_key": "",
                "cycle_label": "",
                "general_review_day": 0,
                "days": None,
            },
        ):
            calendar = config_source.load_validation_calendar()

        self.assertEqual(calendar["cycle_key"], "default")
        self.assertEqual(calendar["cycle_label"], "Ciclo de validacao ECG")
        self.assertEqual(calendar["general_review_day"], 30)
        self.assertEqual(calendar["days"], [])

    def test_active_context_uses_environment_overrides(self):
        calendar = {
            "cycle_key": "cycle",
            "cycle_label": "Cycle",
            "cycle_start_date": None,
            "active_day_index": None,
            "general_review_day": 30,
            "days": [],
        }
        with patch.object(config_source, "load_validation_calendar", return_value=calendar), patch.dict(
            os.environ,
            {
                "VALIDATION_CYCLE_DAY": "4",
                "VALIDATION_ACTIVE_DIAGNOSIS": " Ritmo sinusal ",
            },
            clear=True,
        ):
            context = config_source.active_validation_context(date(2026, 7, 21))

        self.assertEqual(context["day_index"], 4)
        self.assertEqual(context["active_standard_diagnosis"], "Ritmo sinusal")
        self.assertTrue(context["is_configured"])
        self.assertFalse(context["is_general_review_day"])

    def test_active_context_uses_calendar_day_and_start_date(self):
        calendar_day = {
            "cycle_key": "cycle",
            "cycle_label": "Cycle",
            "cycle_start_date": None,
            "active_day_index": 2,
            "general_review_day": 30,
            "days": [
                {"day_index": "2", "standard_diagnosis": " Ritmo sinusal "},
            ],
        }
        with patch.object(config_source, "load_validation_calendar", return_value=calendar_day), patch.dict(
            os.environ, {}, clear=True
        ):
            context = config_source.active_validation_context(date(2026, 7, 21))
        self.assertEqual(context["day_index"], 2)
        self.assertEqual(context["active_standard_diagnosis"], "Ritmo sinusal")

        calendar_start = {
            **calendar_day,
            "cycle_start_date": "2026-07-01",
            "active_day_index": None,
            "general_review_day": 5,
            "days": [],
        }
        with patch.object(config_source, "load_validation_calendar", return_value=calendar_start), patch.dict(
            os.environ, {}, clear=True
        ):
            general_context = config_source.active_validation_context(date(2026, 7, 5))
        self.assertEqual(general_context["day_index"], 5)
        self.assertTrue(general_context["is_general_review_day"])
        self.assertTrue(general_context["is_configured"])

    def test_active_context_can_be_unconfigured(self):
        calendar = {
            "cycle_key": "cycle",
            "cycle_label": "Cycle",
            "cycle_start_date": None,
            "active_day_index": None,
            "general_review_day": 30,
            "days": [],
        }
        with patch.object(config_source, "load_validation_calendar", return_value=calendar), patch.dict(
            os.environ, {}, clear=True
        ):
            context = config_source.active_validation_context(date(2026, 7, 21))
        self.assertIsNone(context["day_index"])
        self.assertFalse(context["is_configured"])

    def test_support_contact_filters_channels_and_accepts_environment_override(self):
        configured = {
            "title": "Support",
            "description": "Contact us",
            "channels": [
                {"label": " Email ", "type": " email ", "value": " help@example.org "},
                {"label": "", "type": "text", "value": "ignored"},
            ],
        }
        with patch.object(config_source, "_load_json", return_value=configured), patch.dict(
            os.environ, {}, clear=True
        ):
            contact = config_source.load_support_contact()
        self.assertEqual(
            contact["channels"],
            [{"label": "Email", "type": "email", "value": "help@example.org"}],
        )

        with patch.object(config_source, "_load_json", return_value=configured.copy()), patch.dict(
            os.environ,
            {
                "SUPPORT_CONTACT_LABEL": " Telefone ",
                "SUPPORT_CONTACT_VALUE": " 555-0100 ",
                "SUPPORT_CONTACT_TYPE": " ",
            },
            clear=True,
        ):
            overridden = config_source.load_support_contact()
        self.assertEqual(
            overridden["channels"],
            [{"label": "Telefone", "type": "text", "value": "555-0100"}],
        )


if __name__ == "__main__":
    unittest.main()
