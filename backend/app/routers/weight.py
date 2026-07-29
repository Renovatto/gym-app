from fastapi import APIRouter, HTTPException, status
from sqlmodel import asc, select

from ..deps import CurrentUser, SessionDep
from ..models import Profile, WeightLog
from ..schemas import (
    BodyCompositionPanelOut,
    BodyFatBandOut,
    BodyFatTargetIn,
    WeightHistoryOut,
    WeightLogIn,
    WeightLogOut,
)
from ..services import body_composition as bc

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


# --- Painel de composicao corporal ----------------------------------------


@router.get("/body-composition", response_model=BodyCompositionPanelOut)
def body_composition_panel(user: CurrentUser, session: SessionDep) -> BodyCompositionPanelOut:
    """A ultima pesagem com bioimpedancia, ja com regua de referencia, tendencia e a
    faixa de peso do alvo escolhido. O IMC diz que nao avalia composicao corporal -
    este painel e o que cumpre essa promessa."""
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="PROFILE_REQUIRED")

    gauge_min, gauge_max = bc.gauge_range(profile.sex)
    bands = [
        BodyFatBandOut(key=key, from_pct=start, to_pct=end)
        for key, start, end in bc.reference_bands(profile.sex)
    ]
    panel = BodyCompositionPanelOut(
        bands=bands,
        gauge_min=gauge_min,
        gauge_max=gauge_max,
        target_fat_percentage=profile.body_fat_target_pct,
    )

    logs = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user.id)
        .order_by(asc(WeightLog.logged_at), asc(WeightLog.id))
    ).all()
    latest = _find_latest_body_composition(list(logs))
    if latest is None:
        return panel  # nunca pesou na balanca de bioimpedancia: so a regua vazia

    lean_kg = bc.lean_mass_kg(latest)
    panel.measured_at = latest.logged_at
    panel.weight_kg = latest.weight_kg
    panel.fat_percentage = latest.fat_percentage
    panel.fat_mass_kg = bc.fat_mass_kg(latest)
    panel.lean_mass_kg = lean_kg
    panel.visceral_fat_index = latest.visceral_fat_index
    panel.water_percentage = latest.water_percentage
    if latest.fat_percentage is not None:
        panel.band_key = bc.classify_body_fat(latest.fat_percentage, profile.sex)

    previous = bc.previous_for_trend(list(logs), latest)
    if previous is not None:
        panel.trend_days = (latest.logged_at.replace(tzinfo=None) - previous.logged_at.replace(tzinfo=None)).days
        if latest.fat_percentage is not None and previous.fat_percentage is not None:
            panel.fat_percentage_delta = round(latest.fat_percentage - previous.fat_percentage, 1)
        previous_lean = bc.lean_mass_kg(previous)
        if lean_kg is not None and previous_lean is not None:
            panel.lean_mass_delta_kg = round(lean_kg - previous_lean, 1)

    if profile.body_fat_target_pct is not None and lean_kg is not None:
        lightest, heaviest = bc.target_weight_range(lean_kg, profile.body_fat_target_pct)
        panel.target_weight_min_kg = lightest
        panel.target_weight_max_kg = heaviest
    return panel


@router.put("/body-composition/target", response_model=BodyCompositionPanelOut)
def set_body_fat_target(
    data: BodyFatTargetIn, user: CurrentUser, session: SessionDep
) -> BodyCompositionPanelOut:
    """Guarda o alvo de gordura escolhido pela pessoa (None limpa). O app nunca
    escolhe um alvo sozinho: quem e dono do corpo decide."""
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="PROFILE_REQUIRED")
    profile.body_fat_target_pct = data.target_fat_percentage
    session.add(profile)
    session.commit()
    return body_composition_panel(user, session)
