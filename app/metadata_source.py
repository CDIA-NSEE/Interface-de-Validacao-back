import os
import sqlite3
from pathlib import Path


DEFAULT_METADATA_PATH = Path(__file__).resolve().parents[2] / "data" / "database" / "metadata.db"


def metadata_database_path() -> Path:
    return Path(os.getenv("METADATA_DATABASE_PATH", DEFAULT_METADATA_PATH))


def load_metadata_records() -> list[dict]:
    path = metadata_database_path()
    if not path.exists():
        return []

    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, archive_name, hash, image_path, processed_at,
                   birth_date, birth_date_flag, sex, sex_flag,
                   exam_date, exam_date_flag, exam_time, exam_time_flag,
                   comments, comments_flag, conclusions, conclusions_flag,
                   notes, notes_flag, age, age_flag, weight, weight_flag,
                   height, height_flag
            FROM metadata
            WHERE error IS NULL OR TRIM(error) = ''
            ORDER BY id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def conclusion_items(conclusions: str | None) -> list[str]:
    if not conclusions:
        return []
    return [line.strip() for line in conclusions.splitlines() if line.strip()]


def load_diagnosis_options() -> list[str]:
    options = []
    for record in load_metadata_records():
        if record["conclusions_flag"]:
            options.extend(conclusion_items(record["conclusions"]))
    return list(dict.fromkeys(options))
