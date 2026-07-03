"""Popula/atualiza o catálogo global de exercícios a partir de seed_exercises.json.
UPSERT por slug: insere novos e atualiza os existentes (grupo, tipo, nível, mídia,
traduções). Só mexe em exercícios globais (user_id IS NULL)."""

import json
from pathlib import Path

from sqlmodel import Session, select

from .db import engine
from .models import (
    Equipment,
    Exercise,
    ExerciseKind,
    ExerciseLevel,
    ExerciseTranslation,
    Food,
    FoodCategory,
    FoodPortion,
    FoodTranslation,
    MuscleGroup,
)

SEED_FILE = Path(__file__).resolve().parent / "seed_exercises.json"
SEED_FOODS_FILE = Path(__file__).resolve().parent / "seed_foods.json"


def seed_exercises() -> None:
    if not SEED_FILE.exists():
        return
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    with Session(engine) as session:
        existing = {
            ex.slug: ex
            for ex in session.exec(select(Exercise).where(Exercise.user_id.is_(None))).all()
        }
        added = 0
        for item in data:
            media = item.get("media_urls") or []
            level = ExerciseLevel(item["level"]) if item.get("level") else None
            ex = existing.get(item["slug"])
            if ex is None:
                ex = Exercise(slug=item["slug"], user_id=None)
                session.add(ex)
                added += 1
            ex.muscle_group = MuscleGroup(item["muscle_group"])
            ex.equipment = Equipment(item["equipment"])
            ex.kind = ExerciseKind(item.get("kind", "strength"))
            ex.level = level
            ex.media_url = media[0] if len(media) > 0 else None
            ex.media_url2 = media[1] if len(media) > 1 else None
            session.flush()

            have = {t.locale for t in ex.translations}
            for locale, name in item["names"].items():
                if locale not in have:
                    session.add(
                        ExerciseTranslation(exercise_id=ex.id, locale=locale, name=name)
                    )
        session.commit()
        print(f"[seed] catálogo sincronizado: {len(data)} exercícios ({added} novos).")


def seed_foods() -> None:
    if not SEED_FOODS_FILE.exists():
        return
    data = json.loads(SEED_FOODS_FILE.read_text(encoding="utf-8"))
    with Session(engine) as session:
        existing = {
            fd.slug: fd
            for fd in session.exec(select(Food).where(Food.user_id.is_(None))).all()
        }
        added = 0
        for item in data:
            fd = existing.get(item["slug"])
            if fd is None:
                fd = Food(slug=item["slug"], user_id=None)
                session.add(fd)
                added += 1
            fd.category = FoodCategory(item["category"])
            fd.kcal = item["kcal"]
            fd.protein_g = item["protein_g"]
            fd.carbs_g = item["carbs_g"]
            fd.fat_g = item["fat_g"]
            fd.default_portion_g = item["default_portion_g"]
            session.flush()

            have_loc = {t.locale for t in fd.translations}
            for locale, name in item["names"].items():
                if locale not in have_loc:
                    session.add(FoodTranslation(food_id=fd.id, locale=locale, name=name))
            if not fd.portions:
                for p in item.get("portions", []):
                    session.add(
                        FoodPortion(food_id=fd.id, label_key=p["label_key"], grams=p["grams"])
                    )
        session.commit()
        print(f"[seed] alimentos sincronizados: {len(data)} ({added} novos).")
