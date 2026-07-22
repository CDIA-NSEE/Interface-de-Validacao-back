import os
from typing import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ecg_review.db")
DEFAULT_POSTGRES_CONNECT_TIMEOUT_SECONDS = 5
MAX_POSTGRES_CONNECT_TIMEOUT_SECONDS = 30


def database_connect_args(
    database_url: str, configured_timeout: str | None
) -> dict[str, int | bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    if database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        try:
            timeout = (
                int(configured_timeout)
                if configured_timeout is not None
                else DEFAULT_POSTGRES_CONNECT_TIMEOUT_SECONDS
            )
        except ValueError:
            timeout = DEFAULT_POSTGRES_CONNECT_TIMEOUT_SECONDS
        return {
            "connect_timeout": min(
                max(timeout, 1), MAX_POSTGRES_CONNECT_TIMEOUT_SECONDS
            )
        }
    return {}


connect_args = database_connect_args(
    DATABASE_URL, os.getenv("DATABASE_CONNECT_TIMEOUT_SECONDS")
)
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_columns()


def reset_db_and_tables() -> None:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    _migrate_columns()


def should_reset_database_on_startup() -> bool:
    configured_value = os.getenv("RESET_DATABASE_ON_STARTUP")
    if configured_value is None:
        return False
    return configured_value.lower() in {"1", "true", "yes", "sim", "on"}


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
