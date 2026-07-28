"""Estimativa de calorias de atividades avulsas (fora do treino de academia).

Formula: kcal = MET * 3.5 * peso_kg / 200 * minutos - equivalente metabolico (MET),
a mesma base usada por relogios e apps de saude para converter intensidade+tempo em
gasto calorico. MET varia por atividade e intensidade (tabela abaixo, valores de
referencia do Compendium of Physical Activities). O usuario sempre pode sobrescrever
o resultado (kcal_is_manual em StandaloneActivity).
"""

from ..models import ActivityIntensity, StandaloneActivityKind

MET_TABLE: dict[StandaloneActivityKind, dict[ActivityIntensity, float]] = {
    StandaloneActivityKind.running: {
        ActivityIntensity.light: 7.0, ActivityIntensity.moderate: 9.8, ActivityIntensity.hard: 12.8
    },
    StandaloneActivityKind.cycling: {
        ActivityIntensity.light: 4.0, ActivityIntensity.moderate: 8.0, ActivityIntensity.hard: 10.8
    },
    StandaloneActivityKind.walking: {
        ActivityIntensity.light: 2.8, ActivityIntensity.moderate: 3.8, ActivityIntensity.hard: 5.0
    },
    StandaloneActivityKind.yoga: {
        ActivityIntensity.light: 2.5, ActivityIntensity.moderate: 4.0, ActivityIntensity.hard: 6.0
    },
    StandaloneActivityKind.pilates: {
        ActivityIntensity.light: 3.0, ActivityIntensity.moderate: 4.0, ActivityIntensity.hard: 5.0
    },
    StandaloneActivityKind.boxing: {
        ActivityIntensity.light: 5.5, ActivityIntensity.moderate: 7.8, ActivityIntensity.hard: 9.5
    },
    StandaloneActivityKind.swimming: {
        ActivityIntensity.light: 5.5, ActivityIntensity.moderate: 8.0, ActivityIntensity.hard: 10.5
    },
    StandaloneActivityKind.dance: {
        ActivityIntensity.light: 3.5, ActivityIntensity.moderate: 5.0, ActivityIntensity.hard: 7.0
    },
    StandaloneActivityKind.other: {
        ActivityIntensity.light: 3.0, ActivityIntensity.moderate: 5.0, ActivityIntensity.hard: 7.0
    },
}

# Atividades onde faz sentido informar distancia (usadas so para exibir o campo km
# no cliente; a estimativa de calorias usa duracao, nao distancia).
DISTANCE_KINDS = {
    StandaloneActivityKind.running,
    StandaloneActivityKind.cycling,
    StandaloneActivityKind.walking,
    StandaloneActivityKind.swimming,
}


def estimate_activity_kcal(
    kind: StandaloneActivityKind, intensity: ActivityIntensity, duration_min: int, weight_kg: float
) -> float:
    met = MET_TABLE[kind][intensity]
    kcal_per_min = met * 3.5 * weight_kg / 200
    return round(kcal_per_min * duration_min, 1)
