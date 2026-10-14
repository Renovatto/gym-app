"""registro alimentar e refeicoes aproximadas

Revision ID: 89c5e4e43a4b
Revises: 018ff10eff0a
Create Date: 2026-10-14 15:37:08.735171

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
# As colunas de texto do SQLModel viram sqlmodel.sql.sqltypes.AutoString nos scripts
# gerados; sem este import a migracao quebra na hora de rodar.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '89c5e4e43a4b'
down_revision: Union[str, Sequence[str], None] = '018ff10eff0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria tabelas adicionais ou restaura os dados preservados na reversao."""
    tables = sa.inspect(op.get_bind()).get_table_names()
    if 'diary_day_reviews_saved' in tables and 'diary_estimates_saved' in tables:
        op.rename_table('diary_day_reviews_saved', 'diary_day_reviews')
        op.rename_table('diary_estimates_saved', 'diary_estimates')
        return
    op.create_table('diary_day_reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('entry_date', sa.Date(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('entries_fingerprint', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'entry_date')
    )
    op.create_index(op.f('ix_diary_day_reviews_entry_date'), 'diary_day_reviews', ['entry_date'], unique=False)
    op.create_index(op.f('ix_diary_day_reviews_user_id'), 'diary_day_reviews', ['user_id'], unique=False)
    op.create_table('diary_estimates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('entry_date', sa.Date(), nullable=False),
    # O enum ja pertence ao diario legado; nao criar nem remover esse tipo.
    sa.Column('meal_type', postgresql.ENUM('breakfast', 'pre_workout', 'post_workout', 'lunch', 'snack', 'dinner', 'supper', 'other', name='mealtype', create_type=False), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('portions', sa.Float(), nullable=False),
    sa.Column('kcal_per_portion', sa.Float(), nullable=True),
    sa.Column('reference', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('logged_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_diary_estimates_entry_date'), 'diary_estimates', ['entry_date'], unique=False)
    op.create_index(op.f('ix_diary_estimates_user_id'), 'diary_estimates', ['user_id'], unique=False)


def downgrade() -> None:
    """Volta a revisao anterior sem apagar aproximacoes nem revisoes do usuario."""
    op.rename_table('diary_estimates', 'diary_estimates_saved')
    op.rename_table('diary_day_reviews', 'diary_day_reviews_saved')
