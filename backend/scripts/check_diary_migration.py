"""Verifica upgrade, reversao e restauracao em uma base local exclusiva de teste.

Executar com GYMAPP_DATABASE_URL apontando para uma base com '_check_' no nome.
Nunca usa a base de desenvolvimento ou producao para ensaiar um downgrade.
"""

from pathlib import Path
import sys
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlmodel import Session

from app.db import engine
from app.models import DiaryDayReview, DiaryEntry, DiaryEstimate, User

PREVIOUS_REVISION = "018ff10eff0a"
BACKEND = Path(__file__).resolve().parents[1]


def main():
    if "_check_" not in engine.url.database or engine.url.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("Use somente uma base local exclusiva com '_check_' no nome.")
    if inspect(engine).get_table_names():
        raise SystemExit("A base de teste precisa estar vazia; nao sobrescrever dados existentes.")

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(config, PREVIOUS_REVISION)
    with engine.begin() as connection:
        user_id = connection.execute(text(
            "INSERT INTO users (email, password_hash, locale, plan, created_at) "
            "VALUES ('rollback@example.invalid', 'test-only', 'pt-BR', 'free', now()) RETURNING id"
        )).scalar_one()
        connection.execute(text(
            "INSERT INTO diary_entries "
            "(user_id, entry_date, meal_type, source, quantity, name_snapshot, kcal, protein_g, carbs_g, fat_g, logged_at) "
            "VALUES (:user_id, '2026-10-13', 'lunch', 'food', 100, 'Registro legado de teste', 500, 20, 50, 10, now())"
        ), {"user_id": user_id})
        legacy_before = connection.execute(text("SELECT * FROM diary_entries")).all()

    command.upgrade(config, "head")
    with Session(engine) as session:
        estimate = DiaryEstimate(user_id=user_id, entry_date=date(2026, 10, 13), meal_type="dinner",
                                 name="Aproximacao preservada", portions=1, kcal_per_portion=700, reference="Teste")
        review = DiaryDayReview(user_id=user_id, entry_date=date(2026, 10, 13), status="complete", entries_fingerprint="teste")
        session.add(estimate)
        session.add(review)
        session.commit()
        estimate_id = estimate.id

    command.downgrade(config, PREVIOUS_REVISION)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT * FROM diary_entries")).all() == legacy_before
        assert connection.execute(text("SELECT name FROM diary_estimates_saved WHERE id = :id"), {"id": estimate_id}).scalar_one() == "Aproximacao preservada"
        assert connection.execute(text("SELECT count(*) FROM diary_day_reviews_saved")).scalar_one() == 1

    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as session:
        assert session.get(DiaryEstimate, estimate_id).name == "Aproximacao preservada"
        assert session.get(User, user_id).email == "rollback@example.invalid"
        assert session.exec(text("SELECT * FROM diary_entries")).all() == legacy_before
    print("Upgrade, downgrade sem perda, restauracao e alinhamento do schema verificados.")


if __name__ == "__main__":
    main()
