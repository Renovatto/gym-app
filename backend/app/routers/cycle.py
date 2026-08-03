"""Acompanhamento do ciclo menstrual (Fase A).

Regras que este router garante (as mesmas do escopo combinado):
- 100% opt-in: nada aqui le o sexo do perfil; quem nunca configurou recebe
  enabled=False e o app se comporta como se a feature nao existisse.
- A fase chega RESOLVIDA para a tela (marcada ou estimada pela data), com a origem
  explicita - a estimativa nunca se disfarca de medicao.
- Erros sao codigos UPPER_SNAKE, nunca texto (o frontend traduz).
"""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import CycleMode, CycleTracking, User, utcnow
from ..schemas import CycleIn, CycleOut
from ..services.cycle import resolve_phase
from ..services.recommend import phase_food_suggestions

router = APIRouter(prefix="/me/cycle", tags=["cycle"])


def _tracking_row(session: SessionDep, user_id: int) -> CycleTracking | None:
    return session.exec(
        select(CycleTracking).where(CycleTracking.user_id == user_id)
    ).first()


def _to_out(
    tracking: CycleTracking | None, day: date, session: SessionDep, user: User
) -> CycleOut:
    phase, source, day_in_cycle, stale = resolve_phase(tracking, day)
    # so busca sugestao quando ha fase: desligado nao custa consulta nenhuma
    suggestions = phase_food_suggestions(session, user, day) if phase else []
    return CycleOut(
        suggestions=suggestions,
        enabled=bool(tracking and tracking.enabled),
        mode=tracking.mode if tracking else CycleMode.manual,
        phase=phase,
        phase_source=source,
        day_in_cycle=day_in_cycle,
        estimate_stale=stale,
        last_period_date=tracking.last_period_date if tracking else None,
        cycle_length_days=tracking.cycle_length_days if tracking else 28,
    )


@router.get("", response_model=CycleOut)
def get_cycle(
    user: CurrentUser,
    session: SessionDep,
    # dia LOCAL do cliente (padrao do projeto): a estimativa por data depende do
    # "hoje" de quem usa, nao do fuso do servidor
    day: date = Query(...),
) -> CycleOut:
    return _to_out(_tracking_row(session, user.id), day, session, user)


@router.put("", response_model=CycleOut)
def save_cycle(
    data: CycleIn,
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(...),
) -> CycleOut:
    """Upsert da configuracao inteira (uma linha por usuaria).

    Validacoes condicionais que o schema nao alcanca: cada modo exige seu campo.
    Desligar NAO apaga a linha - religar volta como estava."""
    if data.enabled and data.mode == CycleMode.manual and data.phase is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="CYCLE_PHASE_REQUIRED")
    if data.enabled and data.mode == CycleMode.by_date and data.last_period_date is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="CYCLE_DATE_REQUIRED")
    # +1 dia de folga para fuso: o "hoje" do cliente pode estar a frente do servidor
    if data.last_period_date is not None and data.last_period_date > day + timedelta(days=1):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="CYCLE_DATE_FUTURE")

    tracking = _tracking_row(session, user.id)
    if tracking is None:
        tracking = CycleTracking(user_id=user.id)
    tracking.enabled = data.enabled
    tracking.mode = data.mode
    tracking.phase = data.phase
    tracking.last_period_date = data.last_period_date
    tracking.cycle_length_days = data.cycle_length_days
    tracking.updated_at = utcnow()
    session.add(tracking)
    session.commit()
    session.refresh(tracking)
    return _to_out(tracking, day, session, user)
