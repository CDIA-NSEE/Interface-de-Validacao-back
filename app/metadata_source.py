import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session

from app.config_source import load_diagnosis_groupings, normalize_text, standardize_diagnosis
from app.metadata_models import METADATA_PAYLOAD_FIELDS, MetadataRecord

try:
    import zstandard as zstd
except ImportError:  # pragma: no cover - optional fallback for environments not installed yet
    zstd = None


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA_PATH = BACKEND_ROOT / "data" / "database" / "metadata.db"
LEGACY_METADATA_PATH = BACKEND_ROOT.parent / "data" / "database" / "metadata.db"


def metadata_database_path() -> Path:
    configured_path = os.getenv("METADATA_DATABASE_PATH")
    if configured_path:
        path = Path(configured_path)
        return path if path.is_absolute() else BACKEND_ROOT / path

    if DEFAULT_METADATA_PATH.exists() or not LEGACY_METADATA_PATH.exists():
        return DEFAULT_METADATA_PATH
    return LEGACY_METADATA_PATH


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _metadata_engine(path: Path):
    return create_engine(_sqlite_url(path), connect_args={"check_same_thread": False})


@contextmanager
def _metadata_session(path: Path) -> Iterator[Session]:
    engine = _metadata_engine(path)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def _metadata_payload_columns():
    return [getattr(MetadataRecord, field) for field in METADATA_PAYLOAD_FIELDS]


def load_metadata_records() -> list[dict]:
    path = metadata_database_path()
    if not path.exists():
        return []

    with _metadata_session(path) as session:
        rows = session.execute(
            select(*_metadata_payload_columns())
            .where(or_(MetadataRecord.error.is_(None), func.trim(MetadataRecord.error) == ""))
            .order_by(MetadataRecord.id)
        ).mappings()
        return [dict(row) for row in rows]


def conclusion_items(conclusions: str | None) -> list[str]:
    if not conclusions:
        return []
    return [line.strip() for line in conclusions.splitlines() if line.strip()]


def load_diagnosis_options() -> list[str]:
    options = []
    seen = set()

    for group in load_diagnosis_groupings():
        standard_text = group["standard_text"]
        normalized_text = normalize_text(standard_text)
        if normalized_text and normalized_text not in seen:
            options.append(standard_text)
            seen.add(normalized_text)

    for record in load_metadata_records():
        if record["conclusions_flag"]:
            for diagnosis in conclusion_items(record["conclusions"]):
                standard_text = standardize_diagnosis(diagnosis)
                normalized_text = normalize_text(standard_text)
                if normalized_text and normalized_text not in seen:
                    options.append(standard_text)
                    seen.add(normalized_text)

    return options


def load_metadata_image(metadata_id: int | None) -> dict | None:
    if not metadata_id or zstd is None:
        return None

    path = metadata_database_path()
    if not path.exists():
        return None

    with _metadata_session(path) as session:
        image_zst = session.scalar(
            select(MetadataRecord.image_zst).where(MetadataRecord.id == metadata_id)
        )

    if not image_zst:
        return None

    try:
        image_bytes = zstd.ZstdDecompressor().decompress(image_zst)
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
