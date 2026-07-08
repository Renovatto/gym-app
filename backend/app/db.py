from collections.abc import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import settings


def _normalize_db_url(url: str) -> str:
    # O Render entrega o Postgres como "postgres://" ou "postgresql://". O SQLAlchemy 2
    # nao aceita "postgres://"; aqui forcamos o dialeto com o driver psycopg (v3).
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


DATABASE_URL = _normalize_db_url(settings.database_url)
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# check_same_thread e exclusivo do SQLite; no Postgres nao passamos connect_args.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
)


if IS_SQLITE:
    # WAL e PRAGMA so existem no SQLite (seriam SQL invalido no Postgres).
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
    "profiles": {
        "cut_intensity": "VARCHAR DEFAULT 'moderate'",
        "first_name": "VARCHAR",
        "last_name": "VARCHAR",
    },
    # Composicao corporal no registro de pesagem (vem da balanca de bioimpedancia).
    "weight_logs": {
        "fat_percentage": "FLOAT",
        "fat_mass_kg": "FLOAT",
        "skeletal_muscle_percentage": "FLOAT",
        "skeletal_muscle_kg": "FLOAT",
        "muscle_percentage": "FLOAT",
        "muscle_mass_kg": "FLOAT",
        "water_percentage": "FLOAT",
        "water_mass_kg": "FLOAT",
        "visceral_fat_index": "FLOAT",
        "scale_bmr_kcal": "INTEGER",
    },
}


def _run_column_migrations() -> None:
    # So faz sentido no SQLite (dev): usa sqlite_master e PRAGMA table_info. No Postgres
    # a base nasce ja com o schema completo via create_all, entao nao ha o que migrar.
    if not IS_SQLITE:
        return
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


def _run_enum_migrations() -> None:
    # So Postgres: os enums do SQLModel viram TIPO NATIVO (ex.: foodcategory). Quando
    # adicionamos um valor novo no enum Python (ex.: 'supplement'), o create_all NAO
    # altera um tipo ja existente - garantimos aqui via ALTER TYPE ... ADD VALUE.
    # (No SQLite o enum e VARCHAR, entao nao ha o que migrar.)
    if IS_SQLITE:
        return
    from sqlalchemy import text

    from .models import FoodCategory

    enum_values: dict[str, list[str]] = {
        "foodcategory": [e.value for e in FoodCategory],
    }
    # ADD VALUE precisa rodar fora de transacao: usamos AUTOCOMMIT.
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        for type_name, values in enum_values.items():
            type_exists = conn.execute(
                text("SELECT 1 FROM pg_type WHERE typname = :t"), {"t": type_name}
            ).first()
            if not type_exists:
                continue  # base nova: o create_all ja criou o tipo com todos os valores
            for value in values:
                # valores vem do nosso proprio enum (confiaveis), entao inline e seguro
                conn.execute(text(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{value}'"))


def init_db() -> None:
    _run_column_migrations()
    SQLModel.metadata.create_all(engine)
    _run_enum_migrations()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
