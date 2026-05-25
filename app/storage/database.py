from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.storage.tables import Base


def _engine_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


engine = create_engine(get_settings().database_url, future=True, **_engine_args(get_settings().database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_compatible_schema()


def _ensure_compatible_schema() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    column_specs = {
        "agent_opinions": {
            "prompt_version": "VARCHAR(64) DEFAULT '' NOT NULL",
        },
        "model_usage_events": {
            "prompt_version": "VARCHAR(64) DEFAULT '' NOT NULL",
        },
    }
    with engine.begin() as conn:
        for table_name, columns in column_specs.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
