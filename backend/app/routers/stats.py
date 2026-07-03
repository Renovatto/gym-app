from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Query
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import DiaryEntry, WaterLog, WorkoutSession
from ..schemas import WeekSummaryOut

router = APIRouter(prefix="/me/summary", tags=["stats"])


def _utc_window(start_day: date, end_day: date, tz_offset_min: int) -> tuple[datetime, datetime]:
    """Janela UTC cobrindo [start_day 00:00, end_day+1 00:00) no fuso local."""
    start_local = datetime.combine(start_day, time.min)
    end_local = datetime.combine(end_day + timedelta(days=1), time.min)
    start = (start_local + timedelta(minutes=tz_offset_min)).replace(tzinfo=timezone.utc)
    end = (end_local + timedelta(minutes=tz_offset_min)).replace(tzinfo=timezone.utc)
    return start, end


@router.get("/week", response_model=WeekSummaryOut)
def week_summary(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (fim da janela de 7 dias)"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente"),
) -> WeekSummaryOut:
    start_day = day - timedelta(days=6)
    start_utc, end_utc = _utc_window(start_day, day, tz_offset)

    # Treinos concluídos e volume na semana
    sessions = session.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .where(WorkoutSession.finished_at.is_not(None))
        .where(WorkoutSession.started_at >= start_utc)
        .where(WorkoutSession.started_at < end_utc)
    ).all()
    total_volume = 0.0
    total_sets = 0
    for ws in sessions:
        for s in ws.sets:
            if s.done:
                total_volume += s.reps * s.weight_kg
                total_sets += 1

    # Dieta: média de kcal por dia com registro (entry_date é dia local)
    diary = session.exec(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user.id)
        .where(DiaryEntry.entry_date >= start_day)
        .where(DiaryEntry.entry_date <= day)
    ).all()
    kcal_by_day: dict[date, float] = defaultdict(float)
    for e in diary:
        kcal_by_day[e.entry_date] += e.kcal
    days_logged = len(kcal_by_day)
    avg_kcal = round(sum(kcal_by_day.values()) / days_logged) if days_logged else 0

    # Água: média por dia com registro
    water = session.exec(
        select(WaterLog)
        .where(WaterLog.user_id == user.id)
        .where(WaterLog.logged_at >= start_utc)
        .where(WaterLog.logged_at < end_utc)
    ).all()
    ml_by_day: dict[date, int] = defaultdict(int)
    for w in water:
        local_dt = w.logged_at - timedelta(minutes=tz_offset)
        ml_by_day[local_dt.date()] += w.amount_ml
    days_water = len(ml_by_day)
    avg_water = round(sum(ml_by_day.values()) / days_water) if days_water else 0

    return WeekSummaryOut(
        workouts=len(sessions),
        total_volume_kg=round(total_volume, 1),
        total_sets=total_sets,
        avg_kcal=avg_kcal,
        days_logged_diet=days_logged,
        avg_water_ml=avg_water,
        days_with_water=days_water,
    )
