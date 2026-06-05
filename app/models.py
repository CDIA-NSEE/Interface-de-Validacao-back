from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Patient(SQLModel, table=True):
    __tablename__ = "patients"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    age: int
    sex: str
    weight: float
    height: float
    bmi: float


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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Diagnosis(SQLModel, table=True):
    __tablename__ = "diagnoses"

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exams.id", index=True)
    name: str
    is_abnormal: bool = Field(default=False)
    region_x: Optional[float] = None
    region_y: Optional[float] = None
    region_width: Optional[float] = None
    region_height: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exams.id", index=True)
    doctor_name: str
    status_before: str
    status_after: str
    review_result: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
