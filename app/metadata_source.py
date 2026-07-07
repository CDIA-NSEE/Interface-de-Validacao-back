import os
import sqlite3
from pathlib import Path

try:
    import zstandard as zstd
except ImportError:  # pragma: no cover - optional fallback for environments not installed yet
    zstd = None


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


def load_metadata_image(metadata_id: int | None) -> dict | None:
    if not metadata_id or zstd is None:
        return None

    path = metadata_database_path()
    if not path.exists():
        return None

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT image_zst FROM metadata WHERE id = ?",
            (metadata_id,),
        ).fetchone()

    if not row or not row[0]:
        return None

    try:
        image_bytes = zstd.ZstdDecompressor().decompress(row[0])
    except zstd.ZstdError:
        return None

    media_type = "application/octet-stream"
    if image_bytes.startswith(b"BM"):
        media_type = "image/bmp"
    elif image_bytes.startswith(b"\x89PNG"):
        media_type = "image/png"
    elif image_bytes.startswith(b"\xff\xd8"):
        media_type = "image/jpeg"

    return {
        "content": image_bytes,
        "media_type": media_type,
    }
