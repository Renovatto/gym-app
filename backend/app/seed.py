"""Popula o catálogo global de exercícios a partir de seed_exercises.json.
Idempotente: só insere exercícios cujo slug ainda não existe."""

import json
from pathlib import Path

from sqlmodel import Session, select

from .db import engine
from .models import Exercise, ExerciseTranslation, MuscleGroup, Equipment

SEED_FILE = Path(__file__).resolve().parent / "seed_exercises.json"


def seed_exercises() -> None:
    if not SEED_FILE.exists():
        return
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    with Session(engine) as session:
        existing = set(
            session.exec(select(Exercise.slug).where(Exercise.user_id.is_(None))).all()
        )
        added = 0
        for item in data:
            if item["slug"] in existing:
                continue
            exercise = Exercise(
                slug=item["slug"],
                muscle_group=MuscleGroup(item["muscle_group"]),
                equipment=Equipment(item["equipment"]),
                media_url=item.get("media_url"),
                user_id=None,
            )
            session.add(exercise)
            session.flush()  # garante exercise.id
            for locale, name in item["names"].items():
                session.add(
                    ExerciseTranslation(exercise_id=exercise.id, locale=locale, name=name)
                )
            added += 1
        session.commit()
        if added:
            print(f"[seed] {added} exercícios inseridos no catálogo.")
