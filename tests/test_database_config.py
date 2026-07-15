import os
import unittest
from unittest.mock import patch

from app.database import should_reset_database_on_startup


class DatabaseConfigTest(unittest.TestCase):
    def test_does_not_reset_database_when_env_is_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(should_reset_database_on_startup())

    def test_resets_database_when_env_is_truthy(self):
        for value in ("1", "true", "yes", "sim", "on"):
            with self.subTest(value=value), patch.dict(
                os.environ,
                {"RESET_DATABASE_ON_STARTUP": value},
                clear=True,
            ):
                self.assertTrue(should_reset_database_on_startup())

    def test_does_not_reset_database_when_env_is_falsey(self):
        for value in ("0", "false", "no", "nao", "off", ""):
            with self.subTest(value=value), patch.dict(
                os.environ,
                {"RESET_DATABASE_ON_STARTUP": value},
                clear=True,
            ):
                self.assertFalse(should_reset_database_on_startup())


if __name__ == "__main__":
    unittest.main()
