import os
import unittest
from unittest.mock import patch

from app.database import database_connect_args, should_reset_database_on_startup


class DatabaseConfigTest(unittest.TestCase):
    def test_postgres_connect_timeout_uses_safe_default(self):
        self.assertEqual(
            database_connect_args("postgresql://user:pass@db/app", None),
            {"connect_timeout": 5},
        )
        self.assertEqual(
            database_connect_args("postgresql://user:pass@db/app", "invalid"),
            {"connect_timeout": 5},
        )

    def test_postgres_connect_timeout_is_bounded(self):
        self.assertEqual(
            database_connect_args("postgresql+psycopg2://user:pass@db/app", "120"),
            {"connect_timeout": 30},
        )
        self.assertEqual(
            database_connect_args("postgresql://user:pass@db/app", "0"),
            {"connect_timeout": 1},
        )

    def test_database_connect_args_preserve_sqlite_and_other_drivers(self):
        self.assertEqual(
            database_connect_args("sqlite:///./ecg_review.db", "10"),
            {"check_same_thread": False},
        )
        self.assertEqual(database_connect_args("mysql://db/app", "10"), {})

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
