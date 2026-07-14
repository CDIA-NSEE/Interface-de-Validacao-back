from __future__ import annotations

from sqlalchemy import LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class MetadataBase(DeclarativeBase):
    pass


class MetadataRecord(MetadataBase):
    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    archive_name: Mapped[str | None]
    hash: Mapped[str | None]
    image_path: Mapped[str | None]
    processed_at: Mapped[str | None]
    birth_date: Mapped[str | None]
    birth_date_flag: Mapped[int | None]
    sex: Mapped[str | None]
    sex_flag: Mapped[int | None]
    exam_date: Mapped[str | None]
    exam_date_flag: Mapped[int | None]
    exam_time: Mapped[str | None]
    exam_time_flag: Mapped[int | None]
    comments: Mapped[str | None]
    comments_flag: Mapped[int | None]
    conclusions: Mapped[str | None]
    conclusions_flag: Mapped[int | None]
    notes: Mapped[str | None]
    notes_flag: Mapped[int | None]
    age: Mapped[int | None]
    age_flag: Mapped[int | None]
    weight: Mapped[float | None]
    weight_flag: Mapped[int | None]
    height: Mapped[float | None]
    height_flag: Mapped[int | None]
    image_zst: Mapped[bytes | None] = mapped_column(LargeBinary)
    error: Mapped[str | None]


METADATA_PAYLOAD_FIELDS = tuple(
    column.name
    for column in MetadataRecord.__table__.columns
    if column.name not in {"error", "image_zst"}
)
