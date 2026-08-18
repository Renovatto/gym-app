"""Tabela login_attempts para limitar tentativas de login

Revision ID: c295fab7ad4d
Revises: 06819c1bdc41
Create Date: 2026-08-17 21:21:00.057883

O autogenerate tambem acusou divergencias antigas e sem relacao com este trabalho
(indices declarados que nunca chegaram ao banco, VARCHAR que virou Enum, colunas
que ficaram nullable). Foram removidas de proposito: sao dividas separadas, e
alterar tipo de coluna em producao merece a sua propria migracao revisada.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# As colunas de texto do SQLModel viram sqlmodel.sql.sqltypes.AutoString nos scripts
# gerados; sem este import a migracao quebra na hora de rodar.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c295fab7ad4d'
down_revision: Union[str, Sequence[str], None] = '06819c1bdc41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'login_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('failures', sa.Integer(), nullable=False),
        sa.Column('window_started_at', sa.DateTime(), nullable=False),
        sa.Column('blocked_until', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    # Unico: cada chave ("email:..." / "ip:...") tem uma linha so, atualizada no
    # lugar. O indice tambem e o caminho de leitura de toda tentativa de login.
    with op.batch_alter_table('login_attempts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_login_attempts_key'), ['key'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('login_attempts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_login_attempts_key'))

    op.drop_table('login_attempts')
