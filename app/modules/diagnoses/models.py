from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Diagnosis(SQLModel, table=True):
    __tablename__ = "diagnoses"

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exams.id", index=True)
    name: str
    source: str = Field(default="original")
    review_status: str = Field(default="pending")
    is_abnormal: bool = Field(default=False)
    region_x: Optional[float] = None
    region_y: Optional[float] = None
    region_width: Optional[float] = None
    region_height: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DiagnosisRegion(SQLModel, table=True):
    __tablename__ = "diagnosis_regions"

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exams.id", index=True)
    diagnosis_id: int = Field(foreign_key="diagnoses.id", index=True)
    x: float
    y: float
    width: float
    height: float
    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    created_by_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DiagnosisValidation(SQLModel, table=True):
    __tablename__ = "diagnosis_validations"

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exams.id", index=True)
    diagnosis_id: int = Field(foreign_key="diagnoses.id", index=True)
    standard_text: str = Field(index=True)
    cycle_key: str = Field(default="default", index=True)
    day_index: Optional[int] = Field(default=None, index=True)
    review_status: str = Field(index=True)
    reviewer_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    reviewer_name: str
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
