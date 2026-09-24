"""inicio do ciclo da rotina separado da criacao

Revision ID: 5553ee741ea0
Revises: 035db8ee5c49
Create Date: 2026-09-24 07:09:18.982453

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# As colunas de texto do SQLModel viram sqlmodel.sql.sqltypes.AutoString nos scripts
# gerados; sem este import a migracao quebra na hora de rodar.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5553ee741ea0'
down_revision: Union[str, Sequence[str], None] = '035db8ee5c49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Inicio do ciclo atual da rotina (a validade de 6 semanas conta daqui).

    Em 3 passos porque a tabela ja tem linhas: cria nullable, preenche com a data de
    criacao (que era de onde a validade contava ate agora - ninguem muda de estado
    com a migracao) e so entao trava NOT NULL.
    """
    op.add_column('routines', sa.Column('cycle_started_at', sa.DateTime(), nullable=True))
    op.execute("UPDATE routines SET cycle_started_at = created_at")
    op.alter_column('routines', 'cycle_started_at', nullable=False)


def downgrade() -> None:
    op.drop_column('routines', 'cycle_started_at')
