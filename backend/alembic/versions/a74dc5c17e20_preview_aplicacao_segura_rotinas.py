"""recibos de aplicacao de propostas de treino

Revision ID: a74dc5c17e20
Revises: df1535bd7985
Create Date: 2026-10-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a74dc5c17e20"
down_revision: Union[str, Sequence[str], None] = "df1535bd7985"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workout_routine_receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("operation_key", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "operation_key"),
    )
    op.create_index(
        op.f("ix_workout_routine_receipts_user_id"),
        "workout_routine_receipts",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_workout_routine_receipts_user_id"),
        table_name="workout_routine_receipts",
    )
    op.drop_table("workout_routine_receipts")
