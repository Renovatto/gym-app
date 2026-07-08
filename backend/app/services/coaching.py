"""Acompanhamento & periodizacao (fase 3).

  - diet_adherence: o quanto voce seguiu o recomendado nos ultimos dias (calorias e
    proteina), sem julgamento - so como bussola.
  - routines_periodization: ha quantas semanas cada rotina esta ativa e se ja passou
    da validade sugerida (mesociclo ~6 semanas) - hora de variar o estimulo.
"""

from collections import defaultdict
from datetime import date, timedelta

from sqlmodel import Session, desc, select

from ..models import DiaryEntry, Profile, Routine, User, WeightLog
from ..schemas import DietAdherenceOut, RoutinePeriodizationOut
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
        weeks = max(0, (today - routine.created_at.date()).days // 7)
        out.append(
            RoutinePeriodizationOut(
                routine_id=routine.id,
                name=routine.name,
                weeks_active=weeks,
                due=weeks >= RENEW_AFTER_WEEKS,
            )
        )
    return out
