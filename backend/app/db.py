from collections.abc import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Migrações leves: create_all cria tabelas novas, mas não adiciona colunas a
# tabelas já existentes. Adicionamos colunas faltantes manualmente (dev/SQLite).
_COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "exercises": {
        "kind": "VARCHAR DEFAULT 'strength'",
        "level": "VARCHAR",
        "media_url2": "VARCHAR",
    },
    "routine_exercises": {"target_duration_min": "INTEGER"},
    "set_logs": {"duration_min": "FLOAT"},
}


def _run_column_migrations() -> None:
    from sqlalchemy import text

    with engine.begin() as conn:
        for table, columns in _COLUMN_MIGRATIONS.items():
            exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": table},
            ).first()
            if not exists:
                continue
            present = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).all()
            }
            for name, ddl in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    _run_column_migrations()
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
