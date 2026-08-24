"""Helpers de exercício: localização de nome e definição dos templates de treino."""

from sqlmodel import Session, select

from ..models import Exercise, ExerciseTranslation, MuscleGroup, MuscleRegion
from ..schemas import ExerciseOut
from .text import normalize_search

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
        muscle_region=exercise.muscle_region,
        equipment=exercise.equipment,
        kind=exercise.kind,
        level=exercise.level,
        media_urls=media,
        is_custom=exercise.user_id is not None,
    )


# Subdivisao de cada MuscleGroup. Fonte unica da verdade da hierarquia - o
# frontend (lib/labels.ts) espelha as MESMAS chaves para montar os chips, do
# jeito que MUSCLE_GROUPS ja espelha os valores de MuscleGroup.
REGIONS_BY_GROUP: dict[MuscleGroup, list[MuscleRegion]] = {
    MuscleGroup.chest: [
        MuscleRegion.chest_upper, MuscleRegion.chest_mid, MuscleRegion.chest_lower,
    ],
    MuscleGroup.back: [
        MuscleRegion.lats, MuscleRegion.upper_back, MuscleRegion.traps,
        MuscleRegion.lower_back,
    ],
    MuscleGroup.shoulders: [
        MuscleRegion.delt_front, MuscleRegion.delt_side, MuscleRegion.delt_rear,
    ],
    MuscleGroup.biceps: [MuscleRegion.biceps, MuscleRegion.forearms],
    MuscleGroup.triceps: [MuscleRegion.triceps_long, MuscleRegion.triceps_lateral],
    MuscleGroup.legs: [
        MuscleRegion.quads, MuscleRegion.hamstrings, MuscleRegion.adductors,
        MuscleRegion.abductors,
    ],
    MuscleGroup.glutes: [MuscleRegion.glute_max, MuscleRegion.glute_med],
    MuscleGroup.abs: [
        MuscleRegion.abs_upper, MuscleRegion.abs_lower, MuscleRegion.obliques,
        MuscleRegion.core,
    ],
    MuscleGroup.calves: [MuscleRegion.gastrocnemius, MuscleRegion.soleus],
    MuscleGroup.cardio: [],
}

# Sinonimos de busca por regiao (pt-BR e en, o par mais usado). Nao sao texto de
# interface - nunca aparecem na tela, so casam com o que a pessoa digita na busca
# que ja existe. Por isso ficam aqui, e nao em messages/*.json.
REGION_ALIASES: dict[MuscleRegion, list[str]] = {
    MuscleRegion.chest_upper: ["peito superior", "clavicular", "upper chest", "incline chest"],
    MuscleRegion.chest_mid: ["peito medio", "esternal", "mid chest", "flat bench"],
    MuscleRegion.chest_lower: ["peito inferior", "declinado", "lower chest", "decline chest"],
    MuscleRegion.lats: ["dorsal", "latissimo", "asa", "lats", "puxada"],
    MuscleRegion.upper_back: ["meio das costas", "romboides", "middle back", "rhomboids"],
    MuscleRegion.traps: ["trapezio", "traps", "encolhimento", "shrug"],
    MuscleRegion.lower_back: ["lombar", "eretores", "lower back", "erector spinae"],
    MuscleRegion.delt_front: ["ombro anterior", "deltoide anterior", "front delt", "anterior deltoid"],
    MuscleRegion.delt_side: ["ombro lateral", "deltoide medial", "side delt", "lateral deltoid"],
    MuscleRegion.delt_rear: ["ombro posterior", "deltoide posterior", "rear delt", "posterior deltoid"],
    MuscleRegion.biceps: ["biceps", "anterior de braco", "biceps brachii"],
    MuscleRegion.forearms: ["antebraco", "braquiorradial", "forearms", "punho", "wrist"],
    MuscleRegion.triceps_long: ["triceps cabeca longa", "triceps testa", "overhead triceps"],
    MuscleRegion.triceps_lateral: ["posterior de braco", "triceps lateral", "triceps pulley"],
    MuscleRegion.quads: ["anterior de coxa", "quadriceps", "quads"],
    MuscleRegion.hamstrings: ["posterior de coxa", "isquiotibiais", "femoral", "hamstrings", "hamstring"],
    MuscleRegion.adductors: ["adutores", "parte interna da coxa", "adductors", "inner thigh"],
    MuscleRegion.abductors: ["abdutores", "parte externa da coxa", "abductors", "outer thigh"],
    MuscleRegion.glute_max: ["gluteo maximo", "bumbum", "hip thrust", "glute max"],
    MuscleRegion.glute_med: ["gluteo medio", "lateral do quadril", "glute med", "hip abduction"],
    MuscleRegion.abs_upper: ["abdomen superior", "abdominal supra", "upper abs"],
    MuscleRegion.abs_lower: ["abdomen inferior", "infra", "lower abs"],
    MuscleRegion.obliques: ["obliquos", "lateral do abdomen", "obliques"],
    MuscleRegion.core: ["core", "estabilizacao", "isometria"],
    MuscleRegion.gastrocnemius: ["gastrocnemio", "panturrilha em pe", "gastrocnemius"],
    MuscleRegion.soleus: ["soleo", "panturrilha sentado", "soleus"],
}


def region_search_match(exercise: Exercise, term: str) -> bool:
    """`term` ja normalizado (normalize_search). True se casa com os apelidos da
    regiao do exercicio - ex.: "femoral" acha exercicios de hamstrings mesmo sem
    a palavra no nome."""
    if exercise.muscle_region is None:
        return False
    aliases = REGION_ALIASES.get(exercise.muscle_region, ())
    return any(term in normalize_search(alias) for alias in aliases)


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
