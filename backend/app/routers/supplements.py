"""Suplementos: os zero-macro (creatina, vitaminas) sao acompanhados por ADESAO
diaria (tomou hoje?) em vez de calorias. Os com macro (whey) seguem no diario como
alimento normal."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, select

from ..deps import CurrentUser, SessionDep
from ..models import Supplement, SupplementLog
from ..schemas import SupplementIn, SupplementOut, SupplementsDayOut

router = APIRouter(prefix="/me/supplements", tags=["supplements"])


def _owned(session: Session, supplement_id: int, user_id: int) -> Supplement:
    supp = session.get(Supplement, supplement_id)
    if supp is None or supp.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SUPPLEMENT_NOT_FOUND")
    return supp


def _supplement_out(session: Session, supp: Supplement, day: date) -> SupplementOut:
    taken = (
        session.exec(
            select(SupplementLog)
            .where(SupplementLog.supplement_id == supp.id)
            .where(SupplementLog.log_date == day)
        ).first()
        is not None
    )
    # consistencia: quantos dos ultimos 7 dias (incluindo o dia consultado) foram tomados
    start = day - timedelta(days=6)
    days = session.exec(
        select(SupplementLog.log_date)
        .where(SupplementLog.supplement_id == supp.id)
        .where(SupplementLog.log_date >= start)
        .where(SupplementLog.log_date <= day)
    ).all()
    return SupplementOut(
        id=supp.id,
        name=supp.name,
        dose=supp.dose,
        active=supp.active,
        taken=taken,
        taken_last_7=len(set(days)),
    )


@router.get("", response_model=SupplementsDayOut)
def list_supplements(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (YYYY-MM-DD)"),
) -> SupplementsDayOut:
    supps = session.exec(
        select(Supplement)
        .where(Supplement.user_id == user.id)
        .where(Supplement.active.is_(True))
        .order_by(Supplement.position, Supplement.id)
    ).all()
    items = [_supplement_out(session, s, day) for s in supps]
    return SupplementsDayOut(
        date=day,
        items=items,
        taken_count=sum(1 for i in items if i.taken),
        total=len(items),
    )


@router.post("", response_model=SupplementOut, status_code=status.HTTP_201_CREATED)
def create_supplement(
    data: SupplementIn,
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local (para calcular tomado/consistencia)"),
) -> SupplementOut:
    # posiciona no fim da lista atual do usuario
    count = len(session.exec(select(Supplement.id).where(Supplement.user_id == user.id)).all())
    supp = Supplement(
        user_id=user.id, name=data.name.strip(), dose=data.dose.strip(), position=count
    )
    session.add(supp)
    session.commit()
    session.refresh(supp)
    return _supplement_out(session, supp, day)


@router.put("/{supplement_id}", response_model=SupplementOut)
def update_supplement(
    supplement_id: int,
    data: SupplementIn,
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(...),
) -> SupplementOut:
    supp = _owned(session, supplement_id, user.id)
    supp.name = data.name.strip()
    supp.dose = data.dose.strip()
    session.add(supp)
    session.commit()
    session.refresh(supp)
    return _supplement_out(session, supp, day)


@router.delete("/{supplement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplement(supplement_id: int, user: CurrentUser, session: SessionDep) -> None:
    supp = _owned(session, supplement_id, user.id)
    session.delete(supp)
    session.commit()


@router.post("/{supplement_id}/log", response_model=SupplementOut)
def mark_taken(
    supplement_id: int,
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(...),
) -> SupplementOut:
    """Marca como tomado no dia (idempotente)."""
    supp = _owned(session, supplement_id, user.id)
    existing = session.exec(
        select(SupplementLog)
        .where(SupplementLog.supplement_id == supp.id)
        .where(SupplementLog.log_date == day)
    ).first()
    if existing is None:
        session.add(SupplementLog(user_id=user.id, supplement_id=supp.id, log_date=day))
        session.commit()
    return _supplement_out(session, supp, day)


@router.delete("/{supplement_id}/log", response_model=SupplementOut)
def unmark_taken(
    supplement_id: int,
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(...),
) -> SupplementOut:
    """Desmarca (remove o registro do dia)."""
    supp = _owned(session, supplement_id, user.id)
    for log in session.exec(
        select(SupplementLog)
        .where(SupplementLog.supplement_id == supp.id)
        .where(SupplementLog.log_date == day)
    ).all():
        session.delete(log)
    session.commit()
    return _supplement_out(session, supp, day)
