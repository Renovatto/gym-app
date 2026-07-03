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
    MuscleGroup,
)

SEED_FILE = Path(__file__).resolve().parent / "seed_exercises.json"


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
