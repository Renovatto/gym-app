"""Motor de conquistas (gamificacao). As definicoes ficam aqui, em codigo; o que
cada usuario desbloqueou fica na tabela user_achievements.

Modelo simples e explicavel: cada conquista tem uma metrica (ex.: total de treinos)
e uma meta (ex.: 10). Fica desbloqueada quando o valor da metrica alcanca a meta.
Isso cobre contagens (treinos, pesagens), streak (semanas seguidas) e marcos de peso.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

# Numero de treinos numa semana para ela contar como "semana ativa" no streak.
STREAK_WEEK_GOAL = 3
# Numero de treinos numa semana para a conquista de "semana completa".
FULL_WEEK_GOAL = 4


@dataclass(frozen=True)
class AchievementDef:
    code: str
    icon: str  # emoji mostrado na medalha
    category: str  # workout | streak | weight | diet
    metric: str  # chave no dicionario de estatisticas (ver build_stats)
    goal: float  # valor da metrica para desbloquear


# Ordem = ordem de exibicao na tela de conquistas.
ACHIEVEMENTS: list[AchievementDef] = [
    AchievementDef("first_workout", "\U0001f44a", "workout", "total_workouts", 1),
    AchievementDef("workouts_10", "\U0001f3cb️", "workout", "total_workouts", 10),
    AchievementDef("workouts_25", "\U0001f4aa", "workout", "total_workouts", 25),
    AchievementDef("workouts_50", "\U0001f947", "workout", "total_workouts", 50),
    AchievementDef("full_week", "\U0001f4c5", "streak", "best_week_workouts", FULL_WEEK_GOAL),
    AchievementDef("streak_3", "\U0001f525", "streak", "weekly_streak", 3),
    AchievementDef("streak_8", "\U0001f31f", "streak", "weekly_streak", 8),
    AchievementDef("first_weigh_in", "⚖️", "weight", "weigh_ins", 1),
    AchievementDef("weigh_ins_10", "\U0001f4c8", "weight", "weigh_ins", 10),
    AchievementDef("lost_1kg", "\U0001f4c9", "weight", "weight_lost_kg", 1),
    AchievementDef("lost_5kg", "\U0001f389", "weight", "weight_lost_kg", 5),
    AchievementDef("first_diet_log", "\U0001f34e", "diet", "diet_days", 1),
    AchievementDef("diet_days_7", "\U0001f957", "diet", "diet_days", 7),
]


def _week_key(day: date) -> tuple[int, int]:
    iso = day.isocalendar()
    return (iso.year, iso.week)


def weekly_streak_and_best(workout_days: list[date], today: date) -> tuple[int, int]:
    """Retorna (streak_de_semanas, melhor_semana).

    - melhor_semana = maior numero de treinos em uma unica semana.
    - streak = semanas consecutivas (indo de hoje para tras) com pelo menos
      STREAK_WEEK_GOAL treinos. A semana atual, se ainda nao atingiu a meta, nao
      quebra o streak (fica "em andamento"); semanas passadas sem a meta quebram.
    """
    counts = Counter(_week_key(day) for day in workout_days)
    best_week = max(counts.values()) if counts else 0

    streak = 0
    cursor = today
    is_current_week = True
    while True:
        week_count = counts.get(_week_key(cursor), 0)
        if week_count >= STREAK_WEEK_GOAL:
            streak += 1
        elif not is_current_week:
            break  # semana passada sem a meta: streak acabou
        is_current_week = False
        cursor = cursor - timedelta(days=7)
        # limite de seguranca: nao ha treinos tao antigos, entao paramos
        if cursor < min(workout_days, default=today) - timedelta(days=7):
            break
    return streak, best_week


def build_stats(
    workout_days: list[date],
    today: date,
    weigh_in_count: int,
    weight_lost_kg: float,
    diet_days: int,
) -> dict[str, float]:
    streak, best_week = weekly_streak_and_best(workout_days, today)
    return {
        "total_workouts": len(workout_days),
        "best_week_workouts": best_week,
        "weekly_streak": streak,
        "weigh_ins": weigh_in_count,
        "weight_lost_kg": max(0.0, weight_lost_kg),
        "diet_days": diet_days,
    }


def is_unlocked(definition: AchievementDef, stats: dict[str, float]) -> bool:
    return stats.get(definition.metric, 0) >= definition.goal
