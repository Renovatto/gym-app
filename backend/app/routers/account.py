"""Endpoints LGPD: exportar todos os dados do usuário e excluir a conta."""

from fastapi import APIRouter, status
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import Profile, WeightLog

router = APIRouter(prefix="/me/account", tags=["account"])


@router.get("/export")
def export_data(user: CurrentUser, session: SessionDep) -> dict:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    weight_logs = session.exec(select(WeightLog).where(WeightLog.user_id == user.id)).all()
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
    }


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: CurrentUser, session: SessionDep) -> None:
    session.delete(user)
    session.commit()
