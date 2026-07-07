import os
from typing import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ecg_review.db")
RESET_DATABASE_ON_STARTUP = os.getenv("RESET_DATABASE_ON_STARTUP")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_columns()


def reset_db_and_tables() -> None:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    _migrate_columns()


def should_reset_database_on_startup() -> bool:
    if RESET_DATABASE_ON_STARTUP is not None:
        return RESET_DATABASE_ON_STARTUP.lower() in {"1", "true", "yes", "sim", "on"}

    return DATABASE_URL == "sqlite:///./ecg_review.db"


def _migrate_columns() -> None:
    definitions = {
        "diagnoses": {
            "source": "VARCHAR NOT NULL DEFAULT 'original'",
            "review_status": "VARCHAR NOT NULL DEFAULT 'pending'",
        },
        "patients": {"birth_date": "VARCHAR"},
        "exams": {
            "metadata_id": "INTEGER",
            "metadata_hash": "VARCHAR",
            "exam_time": "VARCHAR",
            "comments": "VARCHAR",
            "source_notes": "VARCHAR",
        },
        "users": {"role": "VARCHAR NOT NULL DEFAULT 'doctor'"},
    }

    with engine.begin() as connection:
        for table, table_definitions in definitions.items():
            columns = {column["name"] for column in inspect(engine).get_columns(table)}
            for column, definition in table_definitions.items():
                if column not in columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
