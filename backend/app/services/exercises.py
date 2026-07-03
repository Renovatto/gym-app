"""Helpers de exercício: localização de nome e definição dos templates de treino."""

from sqlmodel import Session, select

from ..models import Exercise, ExerciseTranslation
from ..schemas import ExerciseOut

FALLBACK_LOCALE = "en"


def localized_name(session: Session, exercise: Exercise, locale: str) -> str:
    translations = {t.locale: t.name for t in exercise.translations}
    return (
        translations.get(locale)
        or translations.get(FALLBACK_LOCALE)
        or next(iter(translations.values()), exercise.slug)
    )


def to_exercise_out(session: Session, exercise: Exercise, locale: str) -> ExerciseOut:
    media = [u for u in (exercise.media_url, exercise.media_url2) if u]
    return ExerciseOut(
        id=exercise.id,
        slug=exercise.slug,
        name=localized_name(session, exercise, locale),
        muscle_group=exercise.muscle_group,
        equipment=exercise.equipment,
        kind=exercise.kind,
        level=exercise.level,
        media_urls=media,
        is_custom=exercise.user_id is not None,
    )


def has_locale_translation(exercise: Exercise, locale: str) -> bool:
    return any(t.locale == locale for t in exercise.translations)


def exercise_by_slug(session: Session, slug: str) -> Exercise | None:
    return session.exec(
        select(Exercise).where(Exercise.slug == slug).where(Exercise.user_id.is_(None))
    ).first()


# Templates de treino por frequência semanal. Cada rotina lista slugs de exercícios.
TEMPLATES: dict[int, list[tuple[str, list[str]]]] = {
    2: [
        (
            "Full Body A",
            ["barbell-squat", "barbell-bench-press", "bent-over-barbell-row",
             "overhead-press", "barbell-curl", "plank"],
        ),
        (
            "Full Body B",
            ["deadlift", "incline-dumbbell-press", "lat-pulldown",
             "lateral-raise", "triceps-pushdown", "crunches"],
        ),
    ],
    3: [
        ("A — Peito, Ombro e Tríceps",
         ["barbell-bench-press", "incline-dumbbell-press", "overhead-press",
          "lateral-raise", "triceps-pushdown", "bench-dips"]),
        ("B — Costas e Bíceps",
         ["deadlift", "pull-ups", "seated-cable-row", "lat-pulldown",
          "barbell-curl", "hammer-curl"]),
        ("C — Pernas e Abdômen",
         ["barbell-squat", "leg-press", "romanian-deadlift", "leg-extension",
          "standing-calf-raise", "hanging-leg-raise"]),
    ],
    4: [
        ("A — Peito e Tríceps",
         ["barbell-bench-press", "incline-dumbbell-press", "cable-crossover",
          "close-grip-bench-press", "triceps-pushdown"]),
        ("B — Costas e Bíceps",
         ["deadlift", "pull-ups", "bent-over-barbell-row", "seated-cable-row",
          "barbell-curl", "hammer-curl"]),
        ("C — Pernas e Glúteos",
         ["barbell-squat", "leg-press", "romanian-deadlift", "hip-thrust",
          "leg-extension", "standing-calf-raise"]),
        ("D — Ombros e Abdômen",
         ["overhead-press", "arnold-press", "lateral-raise", "face-pull",
          "cable-crunch", "plank"]),
    ],
    5: [
        ("A — Peito",
         ["barbell-bench-press", "incline-dumbbell-press", "dumbbell-flyes",
          "cable-crossover", "push-ups"]),
        ("B — Costas",
         ["deadlift", "pull-ups", "bent-over-barbell-row", "seated-cable-row",
          "lat-pulldown"]),
        ("C — Pernas",
         ["barbell-squat", "leg-press", "romanian-deadlift", "lying-leg-curl",
          "leg-extension", "standing-calf-raise"]),
        ("D — Ombros",
         ["overhead-press", "arnold-press", "lateral-raise", "front-raise",
          "reverse-fly", "face-pull"]),
        ("E — Braços e Abdômen",
         ["barbell-curl", "preacher-curl", "hammer-curl", "triceps-pushdown",
          "overhead-triceps-extension", "hanging-leg-raise"]),
    ],
}
