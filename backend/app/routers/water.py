from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import asc, desc, select

from ..deps import CurrentUser, SessionDep
from ..models import Profile, WaterLog
from ..schemas import WaterDayOut, WaterLogIn, WaterLogOut
from ..services.goals import water_goal_ml

router = APIRouter(prefix="/me/water", tags=["water"])

DEFAULT_GOAL_ML = 2500


def _utc_window(day: date, tz_offset_min: int) -> tuple[datetime, datetime]:
    """Janela UTC [início, fim) do dia local. tz_offset_min = Date.getTimezoneOffset()
    do JS (UTC menos hora local, em minutos: 180 para UTC-3)."""
    local_midnight = datetime.combine(day, time.min)
    start = (local_midnight + timedelta(minutes=tz_offset_min)).replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _goal_for(user_id: int, session: SessionDep) -> int:
    from ..models import WeightLog

    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    latest = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user_id)
        .order_by(desc(WeightLog.logged_at), desc(WeightLog.id))
    ).first()
    if profile is not None and latest is not None:
        return water_goal_ml(latest.weight_kg)
    return DEFAULT_GOAL_ML


@router.get("", response_model=WaterDayOut)
def day(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (YYYY-MM-DD)"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente, em minutos"),
) -> WaterDayOut:
    start, end = _utc_window(day, tz_offset)
    logs = session.exec(
        select(WaterLog)
        .where(WaterLog.user_id == user.id)
        .where(WaterLog.logged_at >= start)
        .where(WaterLog.logged_at < end)
        .order_by(asc(WaterLog.logged_at), asc(WaterLog.id))
    ).all()
    return WaterDayOut(
        date=day,
        total_ml=sum(log.amount_ml for log in logs),
        goal_ml=_goal_for(user.id, session),
        logs=logs,
    )


@router.post("", response_model=WaterLogOut, status_code=status.HTTP_201_CREATED)
def add(data: WaterLogIn, user: CurrentUser, session: SessionDep) -> WaterLog:
    log = WaterLog(user_id=user.id, amount_ml=data.amount_ml)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(log_id: int, user: CurrentUser, session: SessionDep) -> None:
    log = session.get(WaterLog, log_id)
    if log is None or log.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="LOG_NOT_FOUND")
    session.delete(log)
    session.commit()
