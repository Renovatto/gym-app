"""Copia os dados reais de um gymapp.db (SQLite) para o Postgres apontado por
GYMAPP_DATABASE_URL. Script de uso unico, para quem esta migrando o dev local de
SQLite para Postgres e quer manter o historico em vez de comecar do zero.

Pre-requisitos, nesta ordem:
  1. Postgres local de pe (docker compose up -d) e vazio.
  2. `alembic upgrade head` ja rodado (cria o schema).
  3. App subido uma vez (roda seed_exercises/seed_foods: povoa o catalogo global
     de exercicios e alimentos com IDs NOVOS, diferentes dos do SQLite antigo).

So depois disso, com o backend PARADO (para nao escrever no banco durante a copia):

    cd backend
    .venv/bin/python -m scripts.migrate_sqlite_to_postgres /caminho/para/gymapp.db

Tudo roda numa transacao so: se qualquer coisa falhar, nada fica gravado.

O QUE NAO E COPIADO:
  - exercises/exercise_translations e foods/food_translations/food_portions do
    catalogo GLOBAL (user_id IS NULL): ja nasceram de novo pelo seed. So mapeamos
    o ID antigo para o novo (por slug) para corrigir as referencias que apontam
    para eles (routine_exercises, set_logs, diary_entries, etc.).
  - login_attempts: contador de tentativas de login, transitorio - copiar
    arrastaria um bloqueio antigo para o ambiente novo.
  - password_reset_tokens: tokens de uso unico que ja expiraram ou expiram sozinhos.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.db import engine as postgres_engine
from app.models import (
    Connection,
    CycleTracking,
    DiaryEntry,
    DietPeriod,
    Exercise,
    ExerciseTranslation,
    Favorite,
    FavoriteKind,
    FeedbackReport,
    Food,
    FoodPortion,
    FoodTranslation,
    Profile,
    Recipe,
    RecipeIngredient,
    Routine,
    RoutineExercise,
    SessionExerciseSwap,
    SetLog,
    ShareOffer,
    SharedItem,
    SharedItemKind,
    StandaloneActivity,
    Supplement,
    SupplementLog,
    User,
    UserAchievement,
    WaterLog,
    WeightLog,
    WorkoutSession,
)

# Tabelas cujo ID e preservado tal e qual (o Postgres esta vazio nelas): depois de
# inserir com o id explicito, a sequence interna do Postgres fica desatualizada e
# precisa ser realinhada, senao o proximo INSERT sem id colide com um id antigo.
TABLES_WITH_PRESERVED_IDS = [
    "users",
    "profiles",
    "weight_logs",
    "water_logs",
    "routines",
    "routine_exercises",
    "workout_sessions",
    "set_logs",
    "standalone_activities",
    "recipes",
    "recipe_ingredients",
    "diary_entries",
    "favorites",
    "feedback_reports",
    "user_achievements",
    "supplements",
    "supplement_logs",
    "diet_periods",
    "connections",
    "share_offers",
    "shared_items",
    "session_exercise_swaps",
    "cycle_tracking",
]


def _catalog_id_map(src: Session, dst: Session, Model, ChildTranslation, fk_field: str, Portion=None):
    """Constroi old_id -> new_id para um catalogo (Exercise ou Food).

    Global (user_id IS NULL): o Postgres ja tem a linha, criada pelo seed com outro
    id -- casamos pelo slug. Custom (user_id preenchido): a linha nao existe ainda
    no Postgres, entao copiamos ela e as traducoes/porcoes, deixando o Postgres
    atribuir um id novo.
    """
    dst_by_slug = {
        row.slug: row.id for row in dst.exec(select(Model).where(Model.user_id.is_(None))).all()
    }
    id_map: dict[int, int] = {}

    src_rows = src.exec(select(Model)).all()
    for row in src_rows:
        if row.user_id is None:
            new_id = dst_by_slug.get(row.slug)
            if new_id is None:
                raise RuntimeError(
                    f"{Model.__name__} global '{row.slug}' nao existe no Postgres -- "
                    "rode o app uma vez (seed) antes de migrar os dados."
                )
            id_map[row.id] = new_id
            continue

        data = row.model_dump(exclude={"id"})
        new_row = Model(**data)
        dst.add(new_row)
        dst.flush()
        id_map[row.id] = new_row.id

        for translation in src.exec(
            select(ChildTranslation).where(getattr(ChildTranslation, fk_field) == row.id)
        ).all():
            t_data = translation.model_dump(exclude={"id", fk_field})
            dst.add(ChildTranslation(**t_data, **{fk_field: new_row.id}))

        if Portion is not None:
            for portion in src.exec(select(Portion).where(getattr(Portion, fk_field) == row.id)).all():
                p_data = portion.model_dump(exclude={"id", fk_field})
                dst.add(Portion(**p_data, **{fk_field: new_row.id}))

    dst.flush()
    return id_map


def _copy_preserving_id(src: Session, dst: Session, Model, remap: dict[str, dict[int, int]] | None = None):
    rows = src.exec(select(Model)).all()
    for row in rows:
        data = row.model_dump()
        if remap:
            for field, id_map in remap.items():
                old = data.get(field)
                if old is not None:
                    data[field] = id_map[old]
        dst.add(Model(**data))
    dst.flush()
    return len(rows)


def migrate(sqlite_path: Path) -> None:
    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")

    with Session(sqlite_engine) as src, Session(postgres_engine) as dst:
        existing_users = dst.exec(select(User.id)).first()
        if existing_users is not None:
            raise RuntimeError(
                "O Postgres ja tem usuarios -- este script e para um banco recem-criado. "
                "Abortando para nao duplicar dados."
            )

        print("Copiando usuarios e perfis...")
        _copy_preserving_id(src, dst, User)
        _copy_preserving_id(src, dst, Profile)
        _copy_preserving_id(src, dst, WeightLog)
        _copy_preserving_id(src, dst, WaterLog)

        print("Mapeando catalogo de exercicios e alimentos...")
        exercise_map = _catalog_id_map(src, dst, Exercise, ExerciseTranslation, "exercise_id")
        food_map = _catalog_id_map(src, dst, Food, FoodTranslation, "food_id", Portion=FoodPortion)

        print("Copiando rotinas e treinos...")
        _copy_preserving_id(src, dst, Routine)
        _copy_preserving_id(src, dst, RoutineExercise, {"exercise_id": exercise_map})
        _copy_preserving_id(src, dst, WorkoutSession)
        _copy_preserving_id(src, dst, SetLog, {"exercise_id": exercise_map})
        _copy_preserving_id(src, dst, SessionExerciseSwap, {"exercise_id": exercise_map})
        _copy_preserving_id(src, dst, StandaloneActivity)

        print("Copiando receitas e diario...")
        _copy_preserving_id(src, dst, Recipe)
        _copy_preserving_id(src, dst, RecipeIngredient, {"food_id": food_map})
        _copy_preserving_id(src, dst, DiaryEntry, {"food_id": food_map})

        print("Copiando favoritos e compartilhamentos...")
        for row in src.exec(select(Favorite)).all():
            data = row.model_dump()
            if row.kind == FavoriteKind.food:
                data["ref_id"] = food_map[row.ref_id]
            dst.add(Favorite(**data))
        dst.flush()

        for row in src.exec(select(ShareOffer)).all():
            data = row.model_dump()
            if row.item_kind == SharedItemKind.food:
                data["item_id"] = food_map[row.item_id]
            dst.add(ShareOffer(**data))
        dst.flush()

        for row in src.exec(select(SharedItem)).all():
            data = row.model_dump()
            if row.item_kind == SharedItemKind.food:
                data["item_id"] = food_map[row.item_id]
                data["source_item_id"] = food_map[row.source_item_id]
            dst.add(SharedItem(**data))
        dst.flush()

        print("Copiando o resto (conquistas, suplementos, dieta, ciclo)...")
        _copy_preserving_id(src, dst, FeedbackReport)
        _copy_preserving_id(src, dst, UserAchievement)
        _copy_preserving_id(src, dst, Supplement)
        _copy_preserving_id(src, dst, SupplementLog)
        _copy_preserving_id(src, dst, DietPeriod)
        _copy_preserving_id(src, dst, Connection)
        _copy_preserving_id(src, dst, CycleTracking)

        print("Realinhando as sequences do Postgres...")
        for table in TABLES_WITH_PRESERVED_IDS:
            dst.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                )
            )

        dst.commit()
        print("Migracao concluida.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_path", type=Path, help="Caminho para o gymapp.db antigo")
    args = parser.parse_args()
    if not args.sqlite_path.exists():
        raise SystemExit(f"Arquivo nao encontrado: {args.sqlite_path}")
    migrate(args.sqlite_path)
