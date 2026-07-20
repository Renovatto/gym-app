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
    AchievementDef("workouts_100", "\U0001f451", "workout", "total_workouts", 100),
    AchievementDef("workouts_200", "\U0001f3c6", "workout", "total_workouts", 200),
    AchievementDef("full_week", "\U0001f4c5", "streak", "best_week_workouts", FULL_WEEK_GOAL),
    AchievementDef("streak_3", "\U0001f525", "streak", "weekly_streak", 3),
    AchievementDef("streak_8", "\U0001f31f", "streak", "weekly_streak", 8),
    AchievementDef("streak_12", "\U00002604️", "streak", "weekly_streak", 12),
    AchievementDef("first_weigh_in", "⚖️", "weight", "weigh_ins", 1),
    AchievementDef("weigh_ins_10", "\U0001f4c8", "weight", "weigh_ins", 10),
    AchievementDef("weigh_ins_25", "\U0001f4ca", "weight", "weigh_ins", 25),
    AchievementDef("weigh_ins_50", "\U0001f3af", "weight", "weigh_ins", 50),
    AchievementDef("lost_1kg", "\U0001f4c9", "weight", "weight_lost_kg", 1),
    AchievementDef("lost_5kg", "\U0001f389", "weight", "weight_lost_kg", 5),
    AchievementDef("lost_10kg", "\U0001f680", "weight", "weight_lost_kg", 10),
    AchievementDef("first_diet_log", "\U0001f34e", "diet", "diet_days", 1),
    AchievementDef("diet_days_7", "\U0001f957", "diet", "diet_days", 7),
    AchievementDef("diet_days_30", "\U0001f37d️", "diet", "diet_days", 30),
    AchievementDef("diet_days_100", "\U0001f3f5️", "diet", "diet_days", 100),
]

# Conquistas cuja meta e alta o bastante para merecer uma celebracao "de marco grande"
# (mais efeitos) em vez da celebracao padrao da categoria.
MILESTONE_CODES: frozenset[str] = frozenset(
    {"workouts_100", "workouts_200", "streak_12", "weigh_ins_50", "lost_10kg", "diet_days_100"}
)


@dataclass(frozen=True)
class TitleTier:
    code: str  # chave para o nome traduzido no frontend (titleContent.ts)
    goal: float  # total_workouts necessario para alcancar este nivel


# Titulo evolutivo: escada fixa baseada SO em total_workouts (comportamento, nunca peso).
# Texto fixo por nivel (nao combinavel) - mais facil de manter qualidade nos 3 idiomas.
TITLE_TIERS: list[TitleTier] = [
    TitleTier("beginner", 0),
    TitleTier("committed", 5),
    TitleTier("consistent", 15),
    TitleTier("dedicated", 30),
    TitleTier("warrior", 50),
    TitleTier("veteran", 75),
    TitleTier("master", 100),
    TitleTier("legend", 200),
]


def compute_title(stats: dict[str, float]) -> tuple[int, float, float | None]:
    """Retorna (indice do nivel atual, total_workouts, meta do PROXIMO nivel ou None
    se ja esta no topo) - usado para o titulo evolutivo e a barra de progresso dele."""
    total = stats.get("total_workouts", 0)
    idx = 0
    for i, tier in enumerate(TITLE_TIERS):
        if total >= tier.goal:
            idx = i
    next_goal = TITLE_TIERS[idx + 1].goal if idx + 1 < len(TITLE_TIERS) else None
    return idx, total, next_goal


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
