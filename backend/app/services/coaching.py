"""Acompanhamento & periodizacao (fase 3).

  - diet_adherence: o quanto voce seguiu o recomendado nos ultimos dias (calorias e
    proteina), sem julgamento - so como bussola.
  - routines_periodization: ha quantas semanas cada rotina esta ativa e se ja passou
    da validade sugerida (mesociclo ~6 semanas) - hora de variar o estimulo.
"""

import random
from collections import defaultdict
from datetime import date, timedelta

from sqlmodel import Session, desc, select

from ..models import DiaryEntry, Exercise, Profile, Routine, User, WeightLog
from ..schemas import (
    DietAdherenceOut,
    RoutinePeriodizationOut,
    RoutineVariationItemOut,
    RoutineVariationOut,
)
from .exercises import to_exercise_out
from .goals import compute_goals

# Validade sugerida de uma rotina de treino (mesociclo). Passou disso, o corpo ja
# acomodou o estimulo: hora de variar/renovar para continuar progredindo.
RENEW_AFTER_WEEKS = 6


def diet_adherence(session: Session, user: User, end: date, window: int = 7) -> DietAdherenceOut:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    latest = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user.id)
        .order_by(desc(WeightLog.logged_at), desc(WeightLog.id))
    ).first()
    if profile is None or latest is None:
        return DietAdherenceOut(
            window=window, logged_days=0, kcal_pct=0, protein_pct=0, has_goal=False
        )

    goals = compute_goals(profile, latest.weight_kg)
    start = end - timedelta(days=window - 1)
    entries = session.exec(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user.id)
        .where(DiaryEntry.entry_date >= start)
        .where(DiaryEntry.entry_date <= end)
    ).all()

    # Agrega por dia (so dias com lancamento contam para a aderencia).
    by_day: dict[date, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for entry in entries:
        by_day[entry.entry_date][0] += entry.kcal
        by_day[entry.entry_date][1] += entry.protein_g

    days = list(by_day.values())
    if not days:
        return DietAdherenceOut(
            window=window, logged_days=0, kcal_pct=0, protein_pct=0, has_goal=True
        )

    # Aderencia calorica = proximidade da meta (1 - erro relativo). Proteina = fracao
    # da meta batida (sem passar de 100%). Media so dos dias registrados.
    kcal_scores = [max(0.0, 1 - abs(kcal - goals.target_kcal) / goals.target_kcal) for kcal, _ in days]
    protein_scores = [
        min(1.0, protein / goals.protein_g) if goals.protein_g else 0.0 for _, protein in days
    ]
    return DietAdherenceOut(
        window=window,
        logged_days=len(days),
        kcal_pct=round(100 * sum(kcal_scores) / len(kcal_scores)),
        protein_pct=round(100 * sum(protein_scores) / len(protein_scores)),
        has_goal=True,
    )


def routines_periodization(
    session: Session, user: User, today: date
) -> list[RoutinePeriodizationOut]:
    routines = session.exec(
        select(Routine).where(Routine.user_id == user.id).order_by(Routine.position)
    ).all()
    out: list[RoutinePeriodizationOut] = []
    for routine in routines:
        started = routine.created_at.date()
        weeks = max(0, (today - started).days // 7)
        out.append(
            RoutinePeriodizationOut(
                routine_id=routine.id,
                name=routine.name,
                started_on=started,
                renew_on=started + timedelta(weeks=RENEW_AFTER_WEEKS),
                weeks_active=weeks,
                weeks_remaining=max(0, RENEW_AFTER_WEEKS - weeks),
                due=weeks >= RENEW_AFTER_WEEKS,
            )
        )
    return out


def routine_variation(session: Session, routine: Routine, locale: str) -> RoutineVariationOut:
    """Propoe uma variacao da rotina: troca cada exercicio por outro do MESMO grupo
    muscular (e mesmo tipo), mantendo o esquema de series. Sem alternativa no grupo,
    mantem o exercicio original. Evita repetir exercicio dentro da mesma variacao."""
    used_ids: set[int] = set()
    items: list[RoutineVariationItemOut] = []
    for item in routine.items:
        original = session.get(Exercise, item.exercise_id)
        if original is None:
            continue
        candidates = session.exec(
            select(Exercise)
            .where((Exercise.user_id.is_(None)) | (Exercise.user_id == routine.user_id))
            .where(Exercise.muscle_group == original.muscle_group)
            .where(Exercise.kind == original.kind)
            .where(Exercise.id != original.id)
        ).all()
        pool = [c for c in candidates if c.id not in used_ids]
        chosen = random.choice(pool) if pool else original
        used_ids.add(chosen.id)
        items.append(
            RoutineVariationItemOut(
                original_exercise=to_exercise_out(session, original, locale),
                new_exercise=to_exercise_out(session, chosen, locale),
                target_sets=item.target_sets,
                target_reps=item.target_reps,
                target_weight_kg=item.target_weight_kg,
                target_duration_min=item.target_duration_min,
                rest_seconds=item.rest_seconds,
            )
        )
    return RoutineVariationOut(routine_id=routine.id, name=routine.name, items=items)
