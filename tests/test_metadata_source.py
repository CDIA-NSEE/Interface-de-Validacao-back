from contextlib import closing
import os
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event

from app import metadata_source


TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / "tmp_tests"

METADATA_COLUMNS = """
    id INTEGER PRIMARY KEY,
    archive_name TEXT,
    hash TEXT,
    image_path TEXT,
    processed_at TEXT,
    birth_date TEXT,
    birth_date_flag INTEGER,
    sex TEXT,
    sex_flag INTEGER,
    exam_date TEXT,
    exam_date_flag INTEGER,
    exam_time TEXT,
    exam_time_flag INTEGER,
    comments TEXT,
    comments_flag INTEGER,
    conclusions TEXT,
    conclusions_flag INTEGER,
    notes TEXT,
    notes_flag INTEGER,
    age INTEGER,
    age_flag INTEGER,
    weight REAL,
    weight_flag INTEGER,
    height REAL,
    height_flag INTEGER,
    image_zst BLOB,
    error TEXT
"""


def _metadata_row(row_id: int, error: str | None = None, image_zst: bytes | None = None) -> dict:
    return {
        "id": row_id,
        "archive_name": f"archive-{row_id}.pdf",
        "hash": f"hash-{row_id}",
        "image_path": f"image-{row_id}.png",
        "processed_at": "2026-07-14T20:00:00",
        "birth_date": "01/01/1980",
        "birth_date_flag": 1,
        "sex": "Feminino",
        "sex_flag": 1,
        "exam_date": "14/07/2026",
        "exam_date_flag": 1,
        "exam_time": "12:34",
        "exam_time_flag": 1,
        "comments": "Sem comentarios",
        "comments_flag": 1,
        "conclusions": "Ritmo sinusal",
        "conclusions_flag": 1,
        "notes": "Notas",
        "notes_flag": 1,
        "age": 46,
        "age_flag": 1,
        "weight": 70.5,
        "weight_flag": 1,
        "height": 1.7,
        "height_flag": 1,
        "image_zst": image_zst,
        "error": error,
    }


class MetadataSourceTest(unittest.TestCase):
    def setUp(self):
        TEST_TEMP_ROOT.mkdir(exist_ok=True)
        self.db_path = TEST_TEMP_ROOT / f"{self._testMethodName}.db"
        if self.db_path.exists():
            self.db_path.unlink()
        self.addCleanup(lambda: self.db_path.exists() and self.db_path.unlink())

    def _create_database(self, rows: list[dict]) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(f"CREATE TABLE metadata ({METADATA_COLUMNS})")
            for row in rows:
                columns = ", ".join(row.keys())
                placeholders = ", ".join(["?"] * len(row))
                connection.execute(
                    f"INSERT INTO metadata ({columns}) VALUES ({placeholders})",
                    tuple(row.values()),
                )
            connection.commit()

    def _with_metadata_path(self):
        return patch.dict(os.environ, {"METADATA_DATABASE_PATH": str(self.db_path)})

    def test_missing_metadata_database_returns_empty_records(self):
        with self._with_metadata_path():
            self.assertEqual(metadata_source.load_metadata_records(), [])

    def test_default_metadata_path_constant_points_to_back_data_directory(self):
        self.assertEqual(
            metadata_source.DEFAULT_METADATA_PATH,
            metadata_source.BACKEND_ROOT / "data" / "database" / "metadata.db",
        )

    def test_metadata_database_path_uses_default_when_present(self):
        default_path = TEST_TEMP_ROOT / "default-metadata.db"
        legacy_path = TEST_TEMP_ROOT / "missing-legacy-metadata.db"
        if default_path.exists():
            default_path.unlink()
        default_path.touch()
        self.addCleanup(lambda: default_path.exists() and default_path.unlink())

        with patch.dict(os.environ, {}, clear=True), patch.object(
            metadata_source, "DEFAULT_METADATA_PATH", default_path
        ), patch.object(metadata_source, "LEGACY_METADATA_PATH", legacy_path):
            self.assertEqual(
                metadata_source.metadata_database_path(),
                default_path,
            )

    def test_metadata_database_path_uses_absolute_env_override(self):
        configured_path = self.db_path

        with patch.dict(os.environ, {"METADATA_DATABASE_PATH": str(configured_path)}, clear=True):
            self.assertEqual(metadata_source.metadata_database_path(), configured_path)

    def test_metadata_database_path_resolves_relative_env_from_back_root(self):
        with patch.dict(
            os.environ,
            {"METADATA_DATABASE_PATH": "data/database/custom-metadata.db"},
            clear=True,
        ):
            self.assertEqual(
                metadata_source.metadata_database_path(),
                metadata_source.BACKEND_ROOT / "data" / "database" / "custom-metadata.db",
            )

    def test_metadata_database_path_falls_back_to_legacy_data_directory(self):
        default_path = TEST_TEMP_ROOT / "missing-default-metadata.db"
        legacy_path = TEST_TEMP_ROOT / "legacy-metadata.db"
        if legacy_path.exists():
            legacy_path.unlink()
        legacy_path.touch()
        self.addCleanup(lambda: legacy_path.exists() and legacy_path.unlink())

        with patch.dict(os.environ, {}, clear=True), patch.object(
            metadata_source, "DEFAULT_METADATA_PATH", default_path
        ), patch.object(metadata_source, "LEGACY_METADATA_PATH", legacy_path):
            self.assertEqual(metadata_source.metadata_database_path(), legacy_path)

    def test_load_metadata_records_filters_errors_and_orders_by_id(self):
        self._create_database(
            [
                _metadata_row(3, error="falha no processamento"),
                _metadata_row(2, error="   "),
                _metadata_row(1, error=None),
            ]
        )

        with self._with_metadata_path():
            records = metadata_source.load_metadata_records()

        self.assertEqual([record["id"] for record in records], [1, 2])
        self.assertNotIn("error", records[0])
        self.assertNotIn("image_zst", records[0])

    def test_load_metadata_records_keeps_seed_contract_fields(self):
        row = _metadata_row(1)
        self._create_database([row])

        with self._with_metadata_path():
            [record] = metadata_source.load_metadata_records()

        expected_record = {key: value for key, value in row.items() if key not in {"error", "image_zst"}}
        self.assertEqual(record, expected_record)

    def test_load_metadata_records_does_not_select_image_blob(self):
        self._create_database([_metadata_row(1, image_zst=b"compressed-image")])
        statements = []
        real_metadata_engine = metadata_source._metadata_engine

        def tracked_metadata_engine(path):
            engine = real_metadata_engine(path)
            event.listen(
                engine,
                "before_cursor_execute",
                lambda conn, cursor, statement, parameters, context, executemany: statements.append(
                    statement
                ),
            )
            return engine

        with self._with_metadata_path(), patch.object(
            metadata_source, "_metadata_engine", tracked_metadata_engine
        ):
            metadata_source.load_metadata_records()

        self.assertNotIn("image_zst", " ".join(statements).lower())

    def test_load_metadata_image_returns_decompressed_image(self):
        if metadata_source.zstd is None:
            self.skipTest("zstandard is not installed")

        image_bytes = b"\x89PNG\r\n"
        compressed = metadata_source.zstd.ZstdCompressor().compress(image_bytes)
        self._create_database([_metadata_row(1, image_zst=compressed)])

        with self._with_metadata_path():
            image = metadata_source.load_metadata_image(1)

        self.assertEqual(image, {"content": image_bytes, "media_type": "image/png"})

    def test_load_metadata_image_returns_none_without_matching_image(self):
        self._create_database([_metadata_row(1, image_zst=None)])

        with self._with_metadata_path():
            self.assertIsNone(metadata_source.load_metadata_image(1))
            self.assertIsNone(metadata_source.load_metadata_image(999))

    def test_load_metadata_image_returns_none_when_database_is_missing(self):
        with self._with_metadata_path():
            self.assertIsNone(metadata_source.load_metadata_image(1))

    def test_load_metadata_image_returns_none_for_corrupted_zstd_blob(self):
        if metadata_source.zstd is None:
            self.skipTest("zstandard is not installed")

        self._create_database([_metadata_row(1, image_zst=b"not-zstd")])

        with self._with_metadata_path():
            self.assertIsNone(metadata_source.load_metadata_image(1))

    def test_load_metadata_image_returns_none_when_zstd_is_unavailable(self):
        self._create_database([_metadata_row(1, image_zst=b"not-used")])

        with self._with_metadata_path(), patch.object(metadata_source, "zstd", None):
            self.assertIsNone(metadata_source.load_metadata_image(1))


if __name__ == "__main__":
    unittest.main()
