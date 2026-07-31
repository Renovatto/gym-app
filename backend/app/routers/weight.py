from fastapi import APIRouter, HTTPException, status
from sqlmodel import asc, select

from ..deps import CurrentUser, SessionDep
from ..models import Profile, WeightLog
from ..schemas import (
    BodyCompositionPanelOut,
    BodyCompSourceIn,
    BodyFatBandOut,
    BodyFatTargetIn,
    WeightHistoryOut,
    WeightLogIn,
    WeightLogOut,
)
from ..services import body_composition as bc

router = APIRouter(prefix="/me/weight", tags=["weight"])


# Campos opcionais repassados da entrada para o modelo (balanca + fita metrica).
# Manter em um so lugar evita esquecer algum campo ao criar o registro.
WEIGH_IN_OPTIONAL_FIELDS = (
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
    # fita metrica
    "waist_cm",
    "neck_cm",
    "hip_cm",
    "arm_cm",
    "thigh_cm",
    "chest_cm",
)

TAPE_FIELDS = ("waist_cm", "neck_cm", "hip_cm", "arm_cm", "thigh_cm", "chest_cm")


def _has_scale_data(log: WeightLog) -> bool:
    return log.fat_percentage is not None or log.visceral_fat_index is not None


def _has_tape_data(log: WeightLog) -> bool:
    return any(getattr(log, field) is not None for field in TAPE_FIELDS)


def _find_latest_body_composition(logs: list[WeightLog]) -> WeightLog | None:
    """Ultimo registro (mais recente) que trouxe composicao corporal - da balanca OU
    da fita. Sem o "ou", uma pesagem so com medidas de fita ficava invisivel: o
    pre-preenchimento do formulario perdia as medidas e o painel a ignorava."""
    for log in reversed(logs):
        if _has_scale_data(log) or _has_tape_data(log):
            return log
    return None


def _find_latest(logs: list[WeightLog], predicate) -> WeightLog | None:
    for log in reversed(logs):
        if predicate(log):
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
    # copia os campos opcionais informados (os nao informados ficam nulos)
    for field_name in WEIGH_IN_OPTIONAL_FIELDS:
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

    # A fonte escolhida manda em TUDO: faixa, marcador, massa magra, tendencia e a
    # faixa de peso do alvo. As duas estimativas continuam viajando juntas para a
    # tela comparar - ambas erram, e eleger uma como "a verdade" seria desonesto.
    fat_pct, fat_source = bc.resolve_fat_percentage(
        latest, profile.sex, profile.height_cm, profile.body_comp_source
    )
    panel.source_preference = profile.body_comp_source
    panel.fat_source = fat_source
    panel.fat_percentage_scale = latest.fat_percentage
    panel.fat_percentage_tape = bc.navy_body_fat_from_log(latest, profile.sex, profile.height_cm)

    panel.measured_at = latest.logged_at
    panel.weight_kg = latest.weight_kg
    panel.fat_percentage = fat_pct
    panel.visceral_fat_index = latest.visceral_fat_index
    panel.water_percentage = latest.water_percentage
    for field_name in TAPE_FIELDS:
        setattr(panel, field_name, getattr(latest, field_name))

    # gordura em kg e massa magra seguem a fonte: com a fita mandando, usar o
    # fat_mass_kg da balanca misturaria as duas leituras no mesmo numero
    lean_kg = None
    if fat_pct is not None:
        panel.band_key = bc.classify_body_fat(fat_pct, profile.sex)
        if fat_source == bc.SOURCE_SCALE:
            panel.fat_mass_kg = bc.fat_mass_kg(latest)
        else:
            panel.fat_mass_kg = round(latest.weight_kg * fat_pct / 100.0, 1)
        lean_kg = round(latest.weight_kg - panel.fat_mass_kg, 1)
    panel.lean_mass_kg = lean_kg

    # cintura tem significado clinico sozinha (cortes da OMS), sem depender de formula
    panel.waist_risk = bc.waist_risk_band(latest.waist_cm, profile.sex)
    increased_cm, high_cm = bc.waist_risk_cutoffs(profile.sex)
    panel.waist_risk_increased_cm = increased_cm
    panel.waist_risk_high_cm = high_cm

    # a pesagem anterior precisa ter a MESMA fonte, senao a variacao e ficticia
    trend_source = fat_source or profile.body_comp_source
    previous = bc.previous_for_trend(
        list(logs),
        latest,
        lambda log: bc.has_source_data(log, profile.sex, profile.height_cm, trend_source),
    )
    if previous is not None:
        panel.trend_days = (
            latest.logged_at.replace(tzinfo=None) - previous.logged_at.replace(tzinfo=None)
        ).days
        previous_pct, _ = bc.resolve_fat_percentage(
            previous, profile.sex, profile.height_cm, trend_source
        )
        if fat_pct is not None and previous_pct is not None:
            panel.fat_percentage_delta = round(fat_pct - previous_pct, 1)
            previous_lean = round(
                previous.weight_kg - previous.weight_kg * previous_pct / 100.0, 1
            )
            if lean_kg is not None:
                panel.lean_mass_delta_kg = round(lean_kg - previous_lean, 1)
        # variacao das medidas de fita na MESMA janela
        for field_name, delta_name in (
            ("waist_cm", "waist_delta_cm"),
            ("arm_cm", "arm_delta_cm"),
            ("thigh_cm", "thigh_delta_cm"),
        ):
            now_value, before_value = getattr(latest, field_name), getattr(previous, field_name)
            if now_value is not None and before_value is not None:
                setattr(panel, delta_name, round(now_value - before_value, 1))

    if profile.body_fat_target_pct is not None and lean_kg is not None:
        lightest, heaviest = bc.target_weight_range(lean_kg, profile.body_fat_target_pct)
        panel.target_weight_min_kg = lightest
        panel.target_weight_max_kg = heaviest
    return panel


@router.put("/body-composition/source", response_model=BodyCompositionPanelOut)
def set_body_comp_source(
    data: BodyCompSourceIn, user: CurrentUser, session: SessionDep
) -> BodyCompositionPanelOut:
    """Escolhe qual fonte manda no painel: balanca, fita ou automatico.

    Existe porque quem nao tem balanca de bioimpedancia so tem a fita - e o painel
    inteiro dependia da balanca, ficando vazio para essas pessoas. Fixar a fonte
    tambem evita trocar de metodo no meio da serie e estragar a tendencia."""
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="PROFILE_REQUIRED")
    profile.body_comp_source = data.source
    session.add(profile)
    session.commit()
    return body_composition_panel(user, session)


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
