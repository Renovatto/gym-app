"""Registro declarado e porcoes aproximadas, sem alterar o diario legado.

As tabelas adicionais podem permanecer no banco durante uma reversao do aplicativo.
O fingerprint invalida uma revisao quando qualquer caminho altera os alimentos,
inclusive copiar refeicao ou aceitar compartilhamento, sem duplicar eventos.
"""

from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
import json

from sqlmodel import Session, select

from ..models import DiaryDayReview, DiaryEntry, DiaryEstimate
from ..schemas import DiaryEstimateOut, DiaryReviewOut


def estimate_kcal(estimate: DiaryEstimate) -> float | None:
    if estimate.kcal_per_portion is None:
        return None
    # Energia da refeicao = kcal da porcao de referencia vezes porcoes consumidas.
    return round(estimate.kcal_per_portion * estimate.portions, 1)


@dataclass
class DayRecord:
    entries: list[DiaryEntry] = field(default_factory=list)
    estimates: list[DiaryEstimate] = field(default_factory=list)
    review: DiaryDayReview | None = None

    @property
    def fingerprint(self) -> str:
        contents = {
            "entries": [
                [entry.id, entry.quantity, entry.kcal, entry.protein_g,
                 entry.carbs_g, entry.fat_g, entry.meal_type, entry.name_snapshot]
                for entry in sorted(self.entries, key=lambda entry: entry.id)
            ],
            "estimates": [
                [estimate.id, estimate.portions, estimate.kcal_per_portion,
                 estimate.meal_type, estimate.name, estimate.reference]
                for estimate in sorted(self.estimates, key=lambda estimate: estimate.id)
            ],
        }
        return sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()

    @property
    def review_status(self) -> str:
        if self.review is None or self.review.entries_fingerprint != self.fingerprint:
            return "unreviewed"
        return self.review.status

    @property
    def has_unknown_energy(self) -> bool:
        return any(estimate.kcal_per_portion is None for estimate in self.estimates)

    @property
    def known_kcal(self) -> float:
        # Soma apenas energia informada; o sinalizador separado preserva o desconhecido.
        return round(
            sum(entry.kcal for entry in self.entries)
            + sum(estimate_kcal(estimate) or 0 for estimate in self.estimates), 1
        )

    @property
    def has_record(self) -> bool:
        return bool(self.entries or self.estimates)

    def review_out(self) -> DiaryReviewOut:
        return DiaryReviewOut(
            status=self.review_status,
            has_unknown_energy=self.has_unknown_energy,
            has_unknown_macros=bool(self.estimates),
        )


def load_day_records(
    session: Session, user_id: int, start: date, end: date
) -> dict[date, DayRecord]:
    records: dict[date, DayRecord] = {}
    for model, attribute in (
        (DiaryEntry, "entries"), (DiaryEstimate, "estimates"), (DiaryDayReview, "review")
    ):
        rows = session.exec(
            select(model).where(model.user_id == user_id)
            .where(model.entry_date >= start).where(model.entry_date <= end)
        ).all()
        for row in rows:
            record = records.setdefault(row.entry_date, DayRecord())
            if attribute == "review":
                record.review = row
            else:
                getattr(record, attribute).append(row)
    return records


def load_day_record(session: Session, user_id: int, day: date) -> DayRecord:
    return load_day_records(session, user_id, day, day).get(day, DayRecord())


def estimate_out(estimate: DiaryEstimate) -> DiaryEstimateOut:
    return DiaryEstimateOut(
        id=estimate.id, entry_date=estimate.entry_date, meal_type=estimate.meal_type,
        name=estimate.name, portions=estimate.portions, kcal=estimate_kcal(estimate),
        kcal_per_portion=estimate.kcal_per_portion, reference=estimate.reference,
    )
