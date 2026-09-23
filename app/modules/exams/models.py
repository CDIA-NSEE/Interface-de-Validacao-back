from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Exam(SQLModel, table=True):
    __tablename__ = "exams"

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_code: str = Field(index=True, unique=True)
    patient_id: int = Field(foreign_key="patients.id")
    exam_date: date = Field(index=True)
    category: str = Field(index=True)
    exam_type: str = Field(index=True)
    status_validation: str = Field(default="nao_validado", index=True)
    review_result: Optional[str] = Field(default=None, index=True)
    image_url: str = Field(default="/sample-ecg.svg")
    metadata_id: Optional[int] = Field(default=None, index=True)
    metadata_hash: Optional[str] = Field(default=None, index=True)
    exam_time: Optional[str] = None
    comments: Optional[str] = None
    source_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExamDraft(SQLModel, table=True):
    __tablename__ = "exam_drafts"
    __table_args__ = (UniqueConstraint("exam_id", "reviewer_id", name="uq_exam_drafts_exam_reviewer"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exams.id", index=True)
    reviewer_id: int = Field(foreign_key="users.id", index=True)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exams.id", index=True)
    doctor_name: str
    status_before: str
    status_after: str
    review_result: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
