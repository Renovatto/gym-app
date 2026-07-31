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


# Migrações leves: create_all cria tabelas novas, mas nunca adiciona coluna a tabela
# que já existe. Adicionamos as faltantes aqui, nos dois bancos. O DDL abaixo precisa
# valer no SQLite E no Postgres - por isso só tipos portáveis (VARCHAR/FLOAT/INTEGER).
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
        "body_fat_target_pct": "FLOAT",
        "body_comp_source": "VARCHAR DEFAULT 'auto'",
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
        # medidas de fita metrica (tiradas a mao, nao pela balanca)
        "waist_cm": "FLOAT",
        "neck_cm": "FLOAT",
        "hip_cm": "FLOAT",
        "arm_cm": "FLOAT",
        "thigh_cm": "FLOAT",
        "chest_cm": "FLOAT",
    },
}


def _table_exists(conn, table: str) -> bool:
    from sqlalchemy import text

    if IS_SQLITE:
        row = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table},
        ).first()
        return row is not None
    return conn.execute(text("SELECT to_regclass(:t)"), {"t": table}).scalar() is not None


def _run_column_migrations() -> None:
    """Adiciona as colunas que entraram depois que a base ja existia.

    Roda nos DOIS bancos. No SQLite perguntamos ao PRAGMA quais colunas ja existem;
    no Postgres deixamos o proprio banco decidir com ADD COLUMN IF NOT EXISTS, que e
    idempotente. Antes isso era so-SQLite, na premissa de que "no Postgres a base
    nasce completa via create_all" - premissa que vale so para base nova: numa base
    que ja rodava, a coluna nova simplesmente nunca aparecia."""
    from sqlalchemy import text

    with engine.begin() as conn:
        for table, columns in _COLUMN_MIGRATIONS.items():
            if not _table_exists(conn, table):
                continue  # base nova: o create_all logo a seguir cria completa
            if IS_SQLITE:
                present = {
                    row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).all()
                }
                for name, ddl in columns.items():
                    if name not in present:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            else:
                for name, ddl in columns.items():
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ddl}")
                    )


def _native_enum_values() -> dict[str, list[str]]:
    """Nome do tipo -> valores, para todo enum usado como coluna de tabela.

    Varremos o metadata em vez de manter uma lista escrita a mao: foi justamente
    uma lista a mao que deixou 'supper'/'pre_workout' de fora quando o MealType
    cresceu, e lancar ceia passou a falhar em producao (no SQLite o enum e VARCHAR
    e aceita qualquer texto, entao o problema so aparecia no Postgres)."""
    from sqlalchemy import Enum as SAEnum

    from . import models  # noqa: F401  (garante o metadata populado)

    values: dict[str, list[str]] = {}
    for table in SQLModel.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, SAEnum) and column.type.name:
                values[column.type.name] = list(column.type.enums)
    return values


def _run_enum_migrations() -> None:
    # So Postgres: os enums do SQLModel viram TIPO NATIVO (ex.: foodcategory). Quando
    # adicionamos um valor novo no enum Python (ex.: 'supplement'), o create_all NAO
    # altera um tipo ja existente - garantimos aqui via ALTER TYPE ... ADD VALUE.
    # (No SQLite o enum e VARCHAR, entao nao ha o que migrar.)
    if IS_SQLITE:
        return
    from sqlalchemy import text

    enum_values = _native_enum_values()
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
