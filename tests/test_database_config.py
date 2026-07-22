import os
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import inspect, text
from sqlmodel import create_engine

from app import database
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

    def test_create_and_reset_database_apply_schema_and_migrations(self):
        with patch.object(database.SQLModel.metadata, "create_all") as create_all, patch.object(
            database.SQLModel.metadata, "drop_all"
        ) as drop_all, patch.object(database, "_migrate_columns") as migrate:
            database.create_db_and_tables()
            create_all.assert_called_once_with(database.engine)
            drop_all.assert_not_called()
            migrate.assert_called_once_with()

            create_all.reset_mock()
            migrate.reset_mock()
            database.reset_db_and_tables()
            drop_all.assert_called_once_with(database.engine)
            create_all.assert_called_once_with(database.engine)
            migrate.assert_called_once_with()

    def test_migrate_columns_updates_legacy_schema(self):
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE diagnoses (id INTEGER PRIMARY KEY)"))
                connection.execute(text("CREATE TABLE patients (id INTEGER PRIMARY KEY)"))
                connection.execute(text("CREATE TABLE exams (id INTEGER PRIMARY KEY)"))
                connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))

            with patch.object(database, "engine", engine):
                database._migrate_columns()

            inspector = inspect(engine)
            self.assertTrue(
                {"source", "review_status"}.issubset(
                    {column["name"] for column in inspector.get_columns("diagnoses")}
                )
            )
            self.assertIn(
                "birth_date",
                {column["name"] for column in inspector.get_columns("patients")},
            )
            self.assertTrue(
                {"metadata_id", "metadata_hash", "exam_time", "comments", "source_notes"}.issubset(
                    {column["name"] for column in inspector.get_columns("exams")}
                )
            )
            self.assertIn(
                "role",
                {column["name"] for column in inspector.get_columns("users")},
            )
        finally:
            engine.dispose()

    def test_get_session_yields_and_closes_session_context(self):
        expected_session = MagicMock()
        session_context = MagicMock()
        session_context.__enter__.return_value = expected_session

        with patch.object(database, "Session", return_value=session_context):
            sessions = database.get_session()
            self.assertIs(next(sessions), expected_session)
            with self.assertRaises(StopIteration):
                next(sessions)

        session_context.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
