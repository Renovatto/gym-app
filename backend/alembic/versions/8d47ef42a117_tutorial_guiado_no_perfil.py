"""tutorial guiado no perfil

Revision ID: 8d47ef42a117
Revises: b2c7e4915a08
Create Date: 2026-08-19 13:04:14.401740

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# As colunas de texto do SQLModel viram sqlmodel.sql.sqltypes.AutoString nos scripts
# gerados; sem este import a migracao quebra na hora de rodar.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '8d47ef42a117'
down_revision: Union[str, Sequence[str], None] = 'b2c7e4915a08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Estado do tutorial guiado, por usuario.

    Os server_default valem para as linhas que JA existem: quem tem conta hoje entra
    com o tutorial ligado e nenhum passo visto, ou seja, tambem vai ver os tours.
    Sem eles o ALTER TABLE quebraria, porque as duas colunas sao NOT NULL.
    """
    op.add_column(
        'profiles',
        sa.Column('tutorial_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        'profiles',
        sa.Column('tutorial_progress', sa.JSON(), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column('profiles', 'tutorial_progress')
    op.drop_column('profiles', 'tutorial_enabled')
