"""criar indices faltantes

Revision ID: b2c7e4915a08
Revises: f8888d54dcd1
Create Date: 2026-08-18

Os indices do baseline nunca chegaram aos bancos que ja existiam antes do Alembic:
o baseline foi STAMPADO (marcado como aplicado), nao executado, entao nenhum dos
seus CREATE INDEX rodou. Esta migracao recria todos de forma idempotente.

CREATE INDEX IF NOT EXISTS vale no SQLite e no Postgres, entao rodar onde o indice
ja existe e no-op: seguro em qualquer banco, independente de quais faltam em cada um.

Sem CONCURRENTLY de proposito. Ele evitaria o lock de escrita, mas exige bloco de
autocommit e, se falhar no meio, deixa um indice INVALID que o IF NOT EXISTS passa a
pular para sempre. Nas tabelas deste app a criacao e questao de milissegundos - o
lock breve custa menos que esse risco.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b2c7e4915a08'
down_revision: Union[str, Sequence[str], None] = 'f8888d54dcd1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Espelho exato dos op.create_index do baseline (06819c1bdc41), na mesma ordem.
# (nome do indice, tabela, colunas, unique)
INDEXES: list[tuple[str, str, list[str], bool]] = [
    ("ix_users_email", "users", ["email"], True),
    ("ix_connections_addressee_user_id", "connections", ["addressee_user_id"], False),
    ("ix_connections_requester_user_id", "connections", ["requester_user_id"], False),
    ("ix_cycle_tracking_user_id", "cycle_tracking", ["user_id"], True),
    ("ix_diet_periods_started_on", "diet_periods", ["started_on"], False),
    ("ix_diet_periods_user_id", "diet_periods", ["user_id"], False),
    ("ix_exercises_kind", "exercises", ["kind"], False),
    ("ix_exercises_level", "exercises", ["level"], False),
    ("ix_exercises_muscle_group", "exercises", ["muscle_group"], False),
    ("ix_exercises_slug", "exercises", ["slug"], False),
    ("ix_favorites_kind", "favorites", ["kind"], False),
    ("ix_favorites_ref_id", "favorites", ["ref_id"], False),
    ("ix_favorites_user_id", "favorites", ["user_id"], False),
    ("ix_feedback_reports_created_at", "feedback_reports", ["created_at"], False),
    ("ix_feedback_reports_module", "feedback_reports", ["module"], False),
    ("ix_feedback_reports_read", "feedback_reports", ["read"], False),
    ("ix_feedback_reports_user_id", "feedback_reports", ["user_id"], False),
    ("ix_foods_category", "foods", ["category"], False),
    ("ix_foods_slug", "foods", ["slug"], False),
    ("ix_password_reset_tokens_token", "password_reset_tokens", ["token"], False),
    ("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"], False),
    ("ix_recipes_user_id", "recipes", ["user_id"], False),
    ("ix_routines_user_id", "routines", ["user_id"], False),
    ("ix_share_offers_from_user_id", "share_offers", ["from_user_id"], False),
    ("ix_share_offers_to_user_id", "share_offers", ["to_user_id"], False),
    ("ix_shared_items_owner_user_id", "shared_items", ["owner_user_id"], False),
    ("ix_standalone_activities_entry_date", "standalone_activities", ["entry_date"], False),
    ("ix_standalone_activities_user_id", "standalone_activities", ["user_id"], False),
    ("ix_supplements_user_id", "supplements", ["user_id"], False),
    ("ix_user_achievements_code", "user_achievements", ["code"], False),
    ("ix_user_achievements_user_id", "user_achievements", ["user_id"], False),
    ("ix_water_logs_logged_at", "water_logs", ["logged_at"], False),
    ("ix_water_logs_user_id", "water_logs", ["user_id"], False),
    ("ix_weight_logs_logged_at", "weight_logs", ["logged_at"], False),
    ("ix_weight_logs_user_id", "weight_logs", ["user_id"], False),
    ("ix_diary_entries_entry_date", "diary_entries", ["entry_date"], False),
    ("ix_diary_entries_user_id", "diary_entries", ["user_id"], False),
    ("ix_exercise_translations_exercise_id", "exercise_translations", ["exercise_id"], False),
    ("ix_exercise_translations_locale", "exercise_translations", ["locale"], False),
    ("ix_food_portions_food_id", "food_portions", ["food_id"], False),
    ("ix_food_translations_food_id", "food_translations", ["food_id"], False),
    ("ix_food_translations_locale", "food_translations", ["locale"], False),
    ("ix_food_translations_name", "food_translations", ["name"], False),
    ("ix_recipe_ingredients_recipe_id", "recipe_ingredients", ["recipe_id"], False),
    ("ix_routine_exercises_routine_id", "routine_exercises", ["routine_id"], False),
    ("ix_supplement_logs_log_date", "supplement_logs", ["log_date"], False),
    ("ix_supplement_logs_supplement_id", "supplement_logs", ["supplement_id"], False),
    ("ix_supplement_logs_user_id", "supplement_logs", ["user_id"], False),
    ("ix_workout_sessions_started_at", "workout_sessions", ["started_at"], False),
    ("ix_workout_sessions_user_id", "workout_sessions", ["user_id"], False),
    ("ix_session_exercise_swaps_session_id", "session_exercise_swaps", ["session_id"], False),
    ("ix_set_logs_exercise_id", "set_logs", ["exercise_id"], False),
    ("ix_set_logs_session_id", "set_logs", ["session_id"], False),
]


def upgrade() -> None:
    for name, table, columns, unique in INDEXES:
        # aspas duplas valem nos dois dialetos e protegem nomes como a coluna "read"
        cols = ", ".join(f'"{c}"' for c in columns)
        kind = "UNIQUE INDEX" if unique else "INDEX"
        op.execute(f'CREATE {kind} IF NOT EXISTS "{name}" ON "{table}" ({cols})')


def downgrade() -> None:
    # DROP ... IF EXISTS pelo mesmo motivo: o estado anterior variava de banco para banco.
    for name, _table, _columns, _unique in reversed(INDEXES):
        op.execute(f'DROP INDEX IF EXISTS "{name}"')
