import unittest
from unittest.mock import patch

from app.main import _cors_origin_regex, _cors_origins


class CorsConfigTest(unittest.TestCase):
    def test_uses_default_origins_when_env_is_unset(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                _cors_origins(),
                [
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    "http://localhost:5174",
                    "http://127.0.0.1:5174",
                    "http://localhost:5175",
                    "http://127.0.0.1:5175",
                ],
            )

    def test_trims_custom_origins_from_csv(self):
        with patch.dict(
            "os.environ",
            {"BACKEND_CORS_ORIGINS": "https://front.example.com, http://localhost:5173"},
            clear=True,
        ):
            self.assertEqual(
                _cors_origins(),
                ["https://front.example.com", "http://localhost:5173"],
            )

    def test_blank_origins_disable_default_origins(self):
        with patch.dict("os.environ", {"BACKEND_CORS_ORIGINS": "   "}, clear=True):
            self.assertEqual(_cors_origins(), [])

    def test_uses_default_origin_regex_when_env_is_unset(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                _cors_origin_regex(),
                r"^http://192\.168\.\d{1,3}\.\d{1,3}:517[3-5]$",
            )

    def test_blank_origin_regex_disables_regex(self):
        with patch.dict("os.environ", {"BACKEND_CORS_ORIGIN_REGEX": "   "}, clear=True):
            self.assertIsNone(_cors_origin_regex())

    def test_uses_custom_origin_regex(self):
        with patch.dict("os.environ", {"BACKEND_CORS_ORIGIN_REGEX": r"^https://.*$"}, clear=True):
            self.assertEqual(_cors_origin_regex(), r"^https://.*$")


if __name__ == "__main__":
    unittest.main()
