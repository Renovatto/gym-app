from collections.abc import Generator
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, create_engine

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


def run_migrations() -> None:
    """Deixa o banco no schema mais recente, rodando o equivalente a "alembic upgrade head".

    Vale para os dois bancos e para qualquer estado: base vazia nasce completa pela
    revisao inicial, base que ja rodava recebe so as revisoes que faltam, e base ja
    atualizada nao muda nada (a chamada e idempotente). Antes disso o schema vinha de
    create_all mais uma lista de ALTER TABLE escrita a mao, que nao tinha como saber
    o que ja havia sido aplicado.

    Os caminhos sao absolutos porque o script_location do alembic.ini e relativo ao
    diretorio de trabalho, e o app pode subir de qualquer lugar.
    """
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(config, "head")


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
