"""Endpoints LGPD: exportar todos os dados do usuário e excluir a conta."""

from fastapi import APIRouter, status
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import CycleTracking, DiaryDayReview, DiaryEntry, DiaryEstimate, Profile, WaterLog, WeightLog

router = APIRouter(prefix="/me/account", tags=["account"])


@router.get("/export")
def export_data(user: CurrentUser, session: SessionDep) -> dict:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    weight_logs = session.exec(select(WeightLog).where(WeightLog.user_id == user.id)).all()
    water_logs = session.exec(select(WaterLog).where(WaterLog.user_id == user.id)).all()
    diary = session.exec(select(DiaryEntry).where(DiaryEntry.user_id == user.id)).all()
    cycle = session.exec(
        select(CycleTracking).where(CycleTracking.user_id == user.id)
    ).first()
    return {
        "user": {
            "email": user.email,
            "locale": user.locale,
            "plan": user.plan,
            "created_at": user.created_at.isoformat(),
        },
        "profile": profile.model_dump(exclude={"id", "user_id"}, mode="json") if profile else None,
        "weight_logs": [
            log.model_dump(exclude={"id", "user_id"}, mode="json") for log in weight_logs
        ],
        "water_logs": [
            log.model_dump(exclude={"id", "user_id"}, mode="json") for log in water_logs
        ],
        "diary_entries": [
            e.model_dump(exclude={"id", "user_id"}, mode="json") for e in diary
        ],
        "diary_estimates": [
            entry.model_dump(exclude={"id", "user_id"}, mode="json")
            for entry in session.exec(select(DiaryEstimate).where(DiaryEstimate.user_id == user.id)).all()
        ],
        "diary_day_reviews": [
            review.model_dump(exclude={"id", "user_id", "entries_fingerprint"}, mode="json")
            for review in session.exec(select(DiaryDayReview).where(DiaryDayReview.user_id == user.id)).all()
        ],
        # dado de saude e dado da pessoa: o export LGPD leva o ciclo junto
        "cycle_tracking": cycle.model_dump(exclude={"id", "user_id"}, mode="json")
        if cycle
        else None,
    }


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: CurrentUser, session: SessionDep) -> None:
    session.delete(user)
    session.commit()
