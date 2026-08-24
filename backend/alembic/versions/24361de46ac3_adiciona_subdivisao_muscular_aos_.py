"""Adiciona subdivisao muscular aos exercicios

Revision ID: 24361de46ac3
Revises: 4ffaac4be64c
Create Date: 2026-08-24 12:46:26.057725

Coluna opcional (NULL permitido): subdivide o muscle_group em regiões mais
específicas (ex.: legs -> hamstrings). Hierarquia em services/exercises.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# As colunas de texto do SQLModel viram sqlmodel.sql.sqltypes.AutoString nos scripts
# gerados; sem este import a migracao quebra na hora de rodar.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '24361de46ac3'
down_revision: Union[str, Sequence[str], None] = '4ffaac4be64c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MUSCLE_REGION_VALUES = (
    'chest_upper', 'chest_mid', 'chest_lower', 'lats', 'upper_back', 'traps',
    'lower_back', 'delt_front', 'delt_side', 'delt_rear', 'biceps', 'forearms',
    'triceps_long', 'triceps_lateral', 'quads', 'hamstrings', 'adductors',
    'abductors', 'glute_max', 'glute_med', 'abs_upper', 'abs_lower', 'obliques',
    'core', 'gastrocnemius', 'soleus',
)


def upgrade() -> None:
    """Upgrade schema."""
    # Tipo enum novo: op.add_column com sa.Enum(...) nao cria o tipo sozinho no
    # Postgres, so referencia o nome - precisa criar explicitamente antes.
    muscle_region = sa.Enum(*MUSCLE_REGION_VALUES, name='muscleregion')
    muscle_region.create(op.get_bind(), checkfirst=True)
    op.add_column('exercises', sa.Column('muscle_region', muscle_region, nullable=True))
    op.create_index(op.f('ix_exercises_muscle_region'), 'exercises', ['muscle_region'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_exercises_muscle_region'), table_name='exercises')
    op.drop_column('exercises', 'muscle_region')
    sa.Enum(name='muscleregion').drop(op.get_bind(), checkfirst=True)
