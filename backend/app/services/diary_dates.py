"""Limites de datas do diario no fuso local informado pelo cliente."""

from datetime import date, timedelta

from fastapi import HTTPException

from ..models import utcnow


def local_today(tz_offset: int = 0) -> date:
    # Date.getTimezoneOffset() mede UTC - local: subtrair converte UTC para o usuario.
    return (utcnow() - timedelta(minutes=tz_offset)).date()


def validate_entry_day(day: date, tz_offset: int = 0) -> None:
    # O diario permite adiantar uma refeicao somente ate o proximo dia local.
    latest_day = local_today(tz_offset) + timedelta(days=1)
    if day > latest_day:
        raise HTTPException(400, detail="DIARY_DAY_LIMIT")
