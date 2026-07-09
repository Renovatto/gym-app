"""Periodo de dieta (fase 3): a 'vigencia' da meta calorica, com data, objetivo e
validade - o equivalente da periodizacao do treino, mas para a dieta.

Renovar cria um periodo novo (o anterior fica inativo). Ao renovar adotando a
manutencao REAL medida pelo TDEE adaptativo, guardamos essa manutencao como override:
a meta passa a sair dela (via compute_goals(maintenance_override=...)) em vez da formula.
"""

from datetime import date, timedelta

from sqlmodel import Session, desc, select

from ..models import DietPeriod, Profile, User, WeightLog
from ..schemas import DietPeriodOut
from .goals import compute_goals

REVIEW_WEEKS = 4  # validade sugerida da meta de dieta (recalibrar a cada ~2-4 semanas)


def _profile_and_weight(session: Session, user_id: int) -> tuple[Profile | None, WeightLog | None]:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    latest = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user_id)
        .order_by(desc(WeightLog.logged_at), desc(WeightLog.id))
    ).first()
    return profile, latest


def active_period(session: Session, user_id: int) -> DietPeriod | None:
    return session.exec(
        select(DietPeriod)
        .where(DietPeriod.user_id == user_id)
        .where(DietPeriod.active.is_(True))
        .order_by(desc(DietPeriod.started_on), desc(DietPeriod.id))
    ).first()


def maintenance_override(session: Session, user_id: int) -> float | None:
    """Manutencao real adotada no periodo ativo (None = meta segue a formula)."""
    period = active_period(session, user_id)
    if period is not None and period.maintenance_kcal is not None:
        return float(period.maintenance_kcal)
    return None


def ensure_period(session: Session, user: User, today: date) -> DietPeriod | None:
    """Garante um periodo ativo: se nao houver, cria a partir do perfil (meta da formula)."""
    period = active_period(session, user.id)
    if period is not None:
        return period
    profile, latest = _profile_and_weight(session, user.id)
    if profile is None or latest is None:
        return None
    goals = compute_goals(profile, latest.weight_kg)
    period = DietPeriod(
        user_id=user.id,
        started_on=today,
        objective=profile.objective,
        review_weeks=REVIEW_WEEKS,
        target_kcal=goals.target_kcal,
        maintenance_kcal=None,
    )
    session.add(period)
    session.commit()
    session.refresh(period)
    return period


def _out(session: Session, user: User, period: DietPeriod, today: date) -> DietPeriodOut:
    profile, latest = _profile_and_weight(session, user.id)
    # Meta efetiva ATUAL: reflete o override do periodo (se houver) e o peso mais recente.
    effective_target = period.target_kcal
    if profile is not None and latest is not None:
        override = float(period.maintenance_kcal) if period.maintenance_kcal is not None else None
        effective_target = compute_goals(
            profile, latest.weight_kg, maintenance_override=override
        ).target_kcal
    review_on = period.started_on + timedelta(weeks=period.review_weeks)
    return DietPeriodOut(
        started_on=period.started_on,
        review_on=review_on,
        objective=period.objective,
        review_weeks=period.review_weeks,
        target_kcal=effective_target,
        maintenance_kcal=period.maintenance_kcal,
        days_active=max(0, (today - period.started_on).days),
        due=today >= review_on,
    )


def period_out(session: Session, user: User, today: date) -> DietPeriodOut | None:
    period = ensure_period(session, user, today)
    if period is None:
        return None
    return _out(session, user, period, today)


def renew(
    session: Session, user: User, today: date, adopt_maintenance_kcal: int | None
) -> DietPeriodOut | None:
    """Inicia um periodo novo. Se adopt_maintenance_kcal vier, a meta passa a sair da
    manutencao real medida (override); senao, segue a formula do perfil atual."""
    profile, latest = _profile_and_weight(session, user.id)
    if profile is None or latest is None:
        return None
    for old in session.exec(
        select(DietPeriod)
        .where(DietPeriod.user_id == user.id)
        .where(DietPeriod.active.is_(True))
    ).all():
        old.active = False
        session.add(old)
    override = float(adopt_maintenance_kcal) if adopt_maintenance_kcal else None
    target = compute_goals(profile, latest.weight_kg, maintenance_override=override).target_kcal
    period = DietPeriod(
        user_id=user.id,
        started_on=today,
        objective=profile.objective,
        review_weeks=REVIEW_WEEKS,
        target_kcal=target,
        maintenance_kcal=adopt_maintenance_kcal,
    )
    session.add(period)
    session.commit()
    session.refresh(period)
    return _out(session, user, period, today)
