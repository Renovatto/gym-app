from fastapi import APIRouter, HTTPException, status
from sqlmodel import asc, select

from ..deps import CurrentUser, SessionDep
from ..models import WeightLog
from ..schemas import WeightHistoryOut, WeightLogIn, WeightLogOut

router = APIRouter(prefix="/me/weight", tags=["weight"])


# Campos de composicao corporal repassados da entrada para o modelo. Manter em um
# so lugar evita esquecer algum campo ao criar o registro.
BODY_COMPOSITION_FIELDS = (
    "fat_percentage",
    "fat_mass_kg",
    "skeletal_muscle_percentage",
    "skeletal_muscle_kg",
    "muscle_percentage",
    "muscle_mass_kg",
    "water_percentage",
    "water_mass_kg",
    "visceral_fat_index",
    "scale_bmr_kcal",
)


def _find_latest_body_composition(logs: list[WeightLog]) -> WeightLog | None:
    """Ultimo registro (mais recente) que trouxe algum dado de composicao corporal.
    Usado para o painel de composicao, ja que nem toda pesagem tem esses dados."""
    for log in reversed(logs):
        if log.fat_percentage is not None or log.visceral_fat_index is not None:
            return log
    return None


@router.get("", response_model=WeightHistoryOut)
def history(user: CurrentUser, session: SessionDep) -> WeightHistoryOut:
    logs = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user.id)
        .order_by(asc(WeightLog.logged_at), asc(WeightLog.id))
    ).all()
    start = logs[0].weight_kg if logs else None
    current = logs[-1].weight_kg if logs else None
    delta = round(current - start, 1) if start is not None and current is not None else None
    return WeightHistoryOut(
        logs=logs,
        current_kg=current,
        start_kg=start,
        delta_kg=delta,
        latest_body_composition=_find_latest_body_composition(logs),
    )


@router.post("", response_model=WeightLogOut, status_code=status.HTTP_201_CREATED)
def add(data: WeightLogIn, user: CurrentUser, session: SessionDep) -> WeightLog:
    log = WeightLog(user_id=user.id, weight_kg=data.weight_kg, source=data.source)
    if data.logged_at is not None:
        log.logged_at = data.logged_at
    # copia os campos de composicao corporal informados (os nao informados ficam nulos)
    for field_name in BODY_COMPOSITION_FIELDS:
        setattr(log, field_name, getattr(data, field_name))
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(log_id: int, user: CurrentUser, session: SessionDep) -> None:
    log = session.get(WeightLog, log_id)
    if log is None or log.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="LOG_NOT_FOUND")
    session.delete(log)
    session.commit()
