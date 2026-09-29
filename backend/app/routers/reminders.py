"""Lembretes: configuracao (Perfil > Lembretes), refeicoes atrasadas de hoje (cartao
da tela inicial) e o "Pulei hoje". As regras moram em services/reminders.py."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import Profile, ReminderLog
from ..schemas import (
    MealSkipIn,
    OverdueMealOut,
    ReminderSettingsIn,
    ReminderSettingsOut,
    RemindersTodayOut,
)
from ..services.reminders import (
    REMINDER_MEALS,
    meal_code,
    offset_converter,
    overdue_meals,
    resolve_zone,
    usual_meal_minutes,
)

router = APIRouter(prefix="/me/reminders", tags=["reminders"])


def _get_profile(session: SessionDep, user_id: int) -> Profile:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="PROFILE_NOT_FOUND")
    return profile


def _local_now(tz_offset: int) -> datetime:
    """Agora na hora local do aparelho (tz_offset = Date.getTimezoneOffset())."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=tz_offset)


def _settings_out(
    session: SessionDep, profile: Profile, day: date, tz_offset: int
) -> ReminderSettingsOut:
    to_local = offset_converter(tz_offset)
    return ReminderSettingsOut(
        meals=profile.reminder_meals,
        weigh_in=profile.reminder_weigh_in,
        streak=profile.reminder_streak,
        usual_meal_minutes={
            meal_type.value: usual_meal_minutes(session, profile.user_id, meal_type, day, to_local)
            for meal_type in REMINDER_MEALS
        },
    )


@router.get("", response_model=ReminderSettingsOut)
def get_reminder_settings(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente"),
) -> ReminderSettingsOut:
    return _settings_out(session, _get_profile(session, user.id), day, tz_offset)


@router.put("", response_model=ReminderSettingsOut)
def save_reminder_settings(
    data: ReminderSettingsIn,
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente"),
) -> ReminderSettingsOut:
    if resolve_zone(data.time_zone) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="INVALID_TIME_ZONE")
    profile = _get_profile(session, user.id)
    profile.reminder_meals = data.meals
    profile.reminder_weigh_in = data.weigh_in
    profile.reminder_streak = data.streak
    profile.time_zone = data.time_zone
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return _settings_out(session, profile, day, tz_offset)


@router.get("/today", response_model=RemindersTodayOut)
def reminders_today(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente"),
    time_zone: str | None = Query(None, description="Fuso IANA do aparelho"),
) -> RemindersTodayOut:
    """Refeicoes atrasadas de hoje, para o cartao da tela inicial.

    Aproveita a chamada (feita a cada abertura da tela inicial) para manter o fuso
    guardado em dia: quem viaja passa a receber os lembretes na hora local nova sem
    precisar abrir a configuracao."""
    profile = _get_profile(session, user.id)
    if time_zone and time_zone != profile.time_zone and resolve_zone(time_zone) is not None:
        profile.time_zone = time_zone
        session.add(profile)
        session.commit()
    if not profile.diet_enabled:
        return RemindersTodayOut(overdue_meals=[])
    meals = overdue_meals(session, user.id, day, _local_now(tz_offset), offset_converter(tz_offset))
    return RemindersTodayOut(
        overdue_meals=[
            OverdueMealOut(meal_type=meal.meal_type, usual_minutes=meal.usual_minutes)
            for meal in meals
        ]
    )


@router.post("/skip", status_code=status.HTTP_204_NO_CONTENT)
def skip_meal(data: MealSkipIn, user: CurrentUser, session: SessionDep) -> None:
    """"Pulei hoje": some o cartao da refeicao e o push dela nao sai mais neste dia.
    Se o push ja tinha saido, a linha vira "skipped" (o cartao tambem precisa sumir)."""
    code = meal_code(data.meal_type)
    log = session.exec(
        select(ReminderLog)
        .where(ReminderLog.user_id == user.id)
        .where(ReminderLog.code == code)
        .where(ReminderLog.local_date == data.day)
    ).first()
    if log is None:
        log = ReminderLog(user_id=user.id, code=code, local_date=data.day, outcome="skipped")
    else:
        log.outcome = "skipped"
    session.add(log)
    session.commit()
