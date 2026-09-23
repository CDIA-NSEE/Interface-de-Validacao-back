from typing import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.settings import get_settings

_settings = get_settings()
DATABASE_URL = _settings.database.url

engine = create_engine(DATABASE_URL, connect_args=_settings.database.connect_args)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_columns()


def reset_db_and_tables() -> None:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    _migrate_columns()


def should_reset_database_on_startup() -> bool:
    return get_settings().database.reset_on_startup


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
