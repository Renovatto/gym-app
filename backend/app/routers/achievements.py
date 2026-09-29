"""Conquistas do usuario (gamificacao). Ao consultar, o motor avalia os dados atuais,
desbloqueia o que foi conquistado (persistindo) e devolve a lista completa."""

from datetime import date, timedelta

from fastapi import APIRouter, Query
from sqlmodel import asc, desc, select

from ..deps import CurrentUser, SessionDep
from ..models import DiaryEntry, Profile, UserAchievement, WeightLog, WorkoutSession
from ..schemas import AchievementOut, AchievementsOut, WeeklyMissionOut
from ..services.achievements import (
    ACHIEVEMENTS,
    STREAK_WEEK_GOAL,
    build_stats,
    build_weekly_missions,
    compute_title,
    is_unlocked,
    same_iso_week,
)

router = APIRouter(prefix="/me/achievements", tags=["achievements"])


@router.get("", response_model=AchievementsOut)
def list_achievements(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente"),
) -> AchievementsOut:
    # Datas locais dos treinos concluidos (para contagem, semana e streak).
    sessions = session.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .where(WorkoutSession.finished_at.is_not(None))
    ).all()
    workout_days = [
        (ws.finished_at - timedelta(minutes=tz_offset)).date() for ws in sessions
    ]

    # Peso: quantidade de pesagens e quanto ja perdeu (primeira menos a atual).
    weight_logs = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user.id)
        .order_by(asc(WeightLog.logged_at), asc(WeightLog.id))
    ).all()
    weigh_in_count = len(weight_logs)
    weight_lost_kg = (
        weight_logs[0].weight_kg - weight_logs[-1].weight_kg if len(weight_logs) >= 2 else 0.0
    )

    # Dieta: numero de dias distintos com algum lancamento.
    diet_dates = session.exec(
        select(DiaryEntry.entry_date).where(DiaryEntry.user_id == user.id)
    ).all()
    diet_days = len(set(diet_dates))

    stats = build_stats(workout_days, day, weigh_in_count, weight_lost_kg, diet_days)

    # Ja desbloqueadas (code -> quando).
    already = {
        ua.code: ua
        for ua in session.exec(
            select(UserAchievement).where(UserAchievement.user_id == user.id)
        ).all()
    }

    newly_unlocked: list[str] = []
    out: list[AchievementOut] = []
    for definition in ACHIEVEMENTS:
        unlocked_now = is_unlocked(definition, stats)
        record = already.get(definition.code)
        if unlocked_now and record is None:
            record = UserAchievement(user_id=user.id, code=definition.code)
            session.add(record)
            newly_unlocked.append(definition.code)
        out.append(
            AchievementOut(
                code=definition.code,
                icon=definition.icon,
                category=definition.category,
                metric=definition.metric,
                unlocked=record is not None,
                unlocked_at=record.unlocked_at if record else None,
                progress_current=round(stats.get(definition.metric, 0), 1),
                progress_goal=definition.goal,
            )
        )
    if newly_unlocked:
        session.commit()

    week_workout_dates = [d for d in workout_days if same_iso_week(d, day)]
    workouts_this_week = len(week_workout_dates)

    # Missoes da semana: pesagens e dias de dieta contados no dia LOCAL, como o resto.
    weigh_ins_this_week = sum(
        1
        for log in weight_logs
        if same_iso_week((log.logged_at - timedelta(minutes=tz_offset)).date(), day)
    )
    diet_days_this_week = sum(1 for d in set(diet_dates) if same_iso_week(d, day))
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    missions = build_weekly_missions(
        workouts_this_week,
        weigh_ins_this_week,
        diet_days_this_week,
        diet_enabled=profile.diet_enabled if profile else False,
    )

    title_tier, title_current, title_next = compute_title(stats)

    return AchievementsOut(
        achievements=out,
        weekly_streak=int(stats["weekly_streak"]),
        workouts_this_week=workouts_this_week,
        streak_week_goal=STREAK_WEEK_GOAL,
        week_workout_days=sorted(set(week_workout_dates)),
        weekly_missions=[
            WeeklyMissionOut(code=mission.code, current=mission.current, goal=mission.goal)
            for mission in missions
        ],
        newly_unlocked=newly_unlocked,
        title_tier=title_tier,
        title_progress_current=title_current,
        title_progress_next=title_next,
    )
