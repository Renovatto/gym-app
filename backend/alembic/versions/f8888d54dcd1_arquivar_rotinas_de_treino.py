"""arquivar rotinas de treino

Revision ID: f8888d54dcd1
Revises: c295fab7ad4d
Create Date: 2026-08-18 15:42:43.334885

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8888d54dcd1'
down_revision: Union[str, Sequence[str], None] = 'c295fab7ad4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Coluna de arquivamento das rotinas de treino.

    Nullable de proposito: NULL = rotina ativa (no ciclo). Toda rotina que ja
    existe continua ativa, entao nao ha backfill.
    """
    with op.batch_alter_table('routines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('archived_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('routines', schema=None) as batch_op:
        batch_op.drop_column('archived_at')
