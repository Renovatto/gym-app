"""Configuracao do Alembic para o gym-app.

Reusa a conexao do proprio app (app/db.py) em vez de repetir a URL aqui: assim a
normalizacao do "postgres://" que o Render entrega vale tambem para as migracoes, e
apontar para outra base e so exportar GYMAPP_DATABASE_URL antes do comando.
"""

from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

import app.models  # noqa: F401  (o import popula SQLModel.metadata com as tabelas)
from app.db import DATABASE_URL, IS_SQLITE, engine

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False para nao desligar o log do uvicorn quando as
    # migracoes rodam no boot do app (main.py), e nao pela linha de comando.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Gera o SQL das migracoes sem conectar no banco (alembic upgrade --sql)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=IS_SQLITE,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migracoes conectando no banco."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # O SQLite nao tem ALTER TABLE completo (nao altera nem remove coluna).
            # O modo batch contorna recriando a tabela por baixo dos panos; no
            # Postgres o ALTER e nativo, entao batch fica desligado.
            render_as_batch=IS_SQLITE,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
