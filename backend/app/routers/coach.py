"""Coach por regras: gera dicas curtas e acionaveis com base nos dados do usuario
(dieta do dia, agua, treino recente, pesagem). Cada regra devolve um codigo que o
frontend traduz. Sem IA: sao regras simples e explicaveis."""

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, desc, select

from ..deps import CurrentUser, SessionDep
from ..models import DiaryEntry, Objective, Profile, WaterLog, WeightLog, WorkoutSession
from ..schemas import CoachNote, CoachOut
from ..services.adaptive import ADAPTIVE_WINDOW_DAYS, MIN_WEIGH_INS
from ..services.dietplan import maintenance_override as diet_maintenance_override
from ..services.goals import compute_goals

router = APIRouter(prefix="/me/coach", tags=["coach"])

# Limiares das regras (em um lugar so, faceis de ajustar).
PROTEIN_MIN_RATIO = 0.8  # abaixo de 80% da meta de proteina => dica
WATER_MIN_RATIO = 0.5  # abaixo de 50% da meta de agua => dica
DAYS_WITHOUT_WORKOUT_HINT = 4  # sem treino ha N dias => dica
MAX_NOTES = 3  # no maximo N dicas para nao poluir a tela


def _local_day_window(day: date, tz_offset_min: int) -> tuple[datetime, datetime]:
    """Janela UTC [inicio, fim) do dia local do usuario."""
    start_local = datetime.combine(day, time.min)
    start = (start_local + timedelta(minutes=tz_offset_min)).replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _weigh_ins_in_adaptive_window(
    session: Session, user_id: int, day: date, tz_offset_min: int
) -> int:
    """Quantas pesagens o usuario tem na janela do TDEE adaptativo.

    E so a CONTAGEM, nao a estimativa: serve para o lembrete de pesagem dizer quanto
    falta, sem pagar o custo de carregar 3 semanas de diario alimentar."""
    start_day = day - timedelta(days=ADAPTIVE_WINDOW_DAYS - 1)
    start_utc, _ = _local_day_window(start_day, tz_offset_min)
    _, end_utc = _local_day_window(day, tz_offset_min)
    logs = session.exec(
        select(WeightLog.id)
        .where(WeightLog.user_id == user_id)
        .where(WeightLog.logged_at >= start_utc)
        .where(WeightLog.logged_at < end_utc)
    ).all()
    return len(logs)


@router.get("", response_model=CoachOut)
def coach_notes(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente"),
) -> CoachOut:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="PROFILE_NOT_FOUND")

    latest_weight = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user.id)
        .order_by(desc(WeightLog.logged_at), desc(WeightLog.id))
    ).first()

    # dias desde a ultima pesagem (para o lembrete de pesagem)
    days_since_weigh_in: int | None = None
    if latest_weight is not None:
        last_local_date = (latest_weight.logged_at - timedelta(minutes=tz_offset)).date()
        days_since_weigh_in = (day - last_local_date).days

    notes: list[CoachNote] = []
    goals = (
        compute_goals(
            profile,
            latest_weight.weight_kg,
            maintenance_override=diet_maintenance_override(session, user.id),
        )
        if latest_weight
        else None
    )

    # --- Regras de dieta (so quando o modulo esta ativo) -------------------
    if profile.diet_enabled and goals is not None:
        diary_today = session.exec(
            select(DiaryEntry)
            .where(DiaryEntry.user_id == user.id)
            .where(DiaryEntry.entry_date == day)
        ).all()
        if not diary_today:
            notes.append(CoachNote(code="LOG_FOOD", severity="info"))
        else:
            protein_today = sum(entry.protein_g for entry in diary_today)
            if protein_today < goals.protein_g * PROTEIN_MIN_RATIO:
                notes.append(CoachNote(code="LOW_PROTEIN", severity="warn"))

    # --- Regra de agua ------------------------------------------------------
    if goals is not None:
        start_utc, end_utc = _local_day_window(day, tz_offset)
        water_today = session.exec(
            select(WaterLog)
            .where(WaterLog.user_id == user.id)
            .where(WaterLog.logged_at >= start_utc)
            .where(WaterLog.logged_at < end_utc)
        ).all()
        total_water_ml = sum(log.amount_ml for log in water_today)
        if total_water_ml < goals.water_ml * WATER_MIN_RATIO:
            notes.append(CoachNote(code="DRINK_WATER", severity="info"))

    # --- Regra de treino ----------------------------------------------------
    has_routines = (
        session.exec(select(WorkoutSession.id).where(WorkoutSession.user_id == user.id)).first()
        is not None
    )
    last_session = session.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .where(WorkoutSession.finished_at.is_not(None))
        .order_by(desc(WorkoutSession.finished_at))
    ).first()
    if has_routines and last_session is not None:
        last_workout_date = (last_session.finished_at - timedelta(minutes=tz_offset)).date()
        if (day - last_workout_date).days >= DAYS_WITHOUT_WORKOUT_HINT:
            notes.append(CoachNote(code="TRAIN", severity="info"))

    # --- Dica fixa de gordura visceral (so no objetivo de perder gordura) ---
    if profile.objective == Objective.lose_fat and len(notes) < MAX_NOTES:
        notes.append(CoachNote(code="VISCERAL_TIP", severity="info"))

    # Progresso de pesagens rumo ao TDEE adaptativo: so faz sentido com a dieta ligada
    # (e de quem estima manutencao) e enquanto faltam pesagens. Atingido o minimo, some -
    # o lembrete volta a ser o generico, sem ficar cobrando quem ja esta em dia.
    weigh_ins_in_window: int | None = None
    if profile.diet_enabled:
        counted = _weigh_ins_in_adaptive_window(session, user.id, day, tz_offset)
        if counted < MIN_WEIGH_INS:
            weigh_ins_in_window = counted

    # dicas com severidade "warn" primeiro
    notes.sort(key=lambda note: 0 if note.severity == "warn" else 1)
    return CoachOut(
        notes=notes[:MAX_NOTES],
        days_since_weigh_in=days_since_weigh_in,
        weigh_ins_in_window=weigh_ins_in_window,
        min_weigh_ins=MIN_WEIGH_INS,
    )
