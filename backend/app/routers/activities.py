from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, asc, desc, select

from ..deps import CurrentUser, SessionDep
from ..models import ActivityIntensity, StandaloneActivity, StandaloneActivityKind, WeightLog
from ..schemas import ActivityEstimateOut, StandaloneActivityIn, StandaloneActivityOut
from ..services.activities import estimate_activity_kcal

router = APIRouter(prefix="/me/activities", tags=["activities"])


def _latest_weight_kg(session: Session, user_id: int) -> float:
    weight = session.exec(
        select(WeightLog.weight_kg)
        .where(WeightLog.user_id == user_id)
        .order_by(desc(WeightLog.logged_at), desc(WeightLog.id))
    ).first()
    if weight is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="PROFILE_REQUIRED")
    return weight


@router.get("/estimate", response_model=ActivityEstimateOut)
def estimate(
    user: CurrentUser,
    session: SessionDep,
    kind: StandaloneActivityKind = Query(...),
    intensity: ActivityIntensity = Query(...),
    duration_min: int = Query(..., gt=0, le=600),
) -> ActivityEstimateOut:
    """Estimativa ao vivo enquanto o usuario ajusta tipo/intensidade/duracao,
    antes de salvar (o valor final so vira definitivo quando ele confirma)."""
    weight_kg = _latest_weight_kg(session, user.id)
    kcal = estimate_activity_kcal(kind, intensity, duration_min, weight_kg)
    return ActivityEstimateOut(kcal=kcal)


@router.get("/days", response_model=list[date])
def activity_days(user: CurrentUser, session: SessionDep) -> list[date]:
    """Dias que tem alguma atividade avulsa, para marcar no calendario de treino
    (o calendario precisa do mes inteiro de uma vez, nao de um dia por vez)."""
    return list(
        session.exec(
            select(StandaloneActivity.entry_date)
            .where(StandaloneActivity.user_id == user.id)
            .distinct()
            .order_by(desc(StandaloneActivity.entry_date))
        ).all()
    )


@router.get("", response_model=list[StandaloneActivityOut])
def list_activities(user: CurrentUser, session: SessionDep, day: date = Query(...)) -> list[StandaloneActivity]:
    return list(
        session.exec(
            select(StandaloneActivity)
            .where(StandaloneActivity.user_id == user.id)
            .where(StandaloneActivity.entry_date == day)
            .order_by(asc(StandaloneActivity.time_of_day), asc(StandaloneActivity.id))
        ).all()
    )


@router.post("", response_model=StandaloneActivityOut, status_code=status.HTTP_201_CREATED)
def add_activity(data: StandaloneActivityIn, user: CurrentUser, session: SessionDep) -> StandaloneActivity:
    if data.kcal is not None:
        kcal, kcal_is_manual = data.kcal, True
    else:
        weight_kg = _latest_weight_kg(session, user.id)
        kcal = estimate_activity_kcal(data.kind, data.intensity, data.duration_min, weight_kg)
        kcal_is_manual = False
    activity = StandaloneActivity(
        user_id=user.id,
        entry_date=data.entry_date,
        time_of_day=data.time_of_day,
        kind=data.kind,
        duration_min=data.duration_min,
        intensity=data.intensity,
        distance_km=data.distance_km,
        kcal=kcal,
        kcal_is_manual=kcal_is_manual,
    )
    session.add(activity)
    session.commit()
    session.refresh(activity)
    return activity


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(activity_id: int, user: CurrentUser, session: SessionDep) -> None:
    activity = session.get(StandaloneActivity, activity_id)
    if activity is None or activity.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ACTIVITY_NOT_FOUND")
    session.delete(activity)
    session.commit()
