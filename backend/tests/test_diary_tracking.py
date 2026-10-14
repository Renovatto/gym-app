"""Integracao em PostgreSQL: cada teste usa savepoints e desfaz seus registros."""

from datetime import date, datetime, timedelta
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session

from app.db import engine
from app.deps import get_current_user, get_session
from app.main import app
from app.models import (
    DiaryEntry, EntrySource, Food, MealType, Profile, ShareOffer,
    ShareOfferMealItem, User, WeightLog,
)


class DiaryTrackingTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(email="diary-tracking-test@example.invalid", password_hash="test-only")
        self.session.add(self.user)
        self.session.flush()
        self.today = date(2026, 10, 14)
        self.yesterday = self.today - timedelta(days=1)
        self.session.add(Profile(
            user_id=self.user.id, height_cm=175, birthdate=date(1985, 1, 1), sex="male",
            activity_level="moderate", objective="maintain", diet_enabled=True,
        ))
        self.session.commit()
        app.dependency_overrides[get_session] = lambda: self.session
        app.dependency_overrides[get_current_user] = lambda: self.user
        # Sem lifespan: os testes nao rodam sementes, migracoes ou tarefas de push.
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def entry(self, day, kcal=2000):
        entry = DiaryEntry(
            user_id=self.user.id, entry_date=day, meal_type=MealType.lunch,
            source=EntrySource.food, quantity=100, name_snapshot="Alimento de teste",
            kcal=kcal, protein_g=100, carbs_g=200, fat_g=50,
        )
        self.session.add(entry)
        self.session.commit()
        return entry

    def diary(self, day=None):
        response = self.client.get('/me/diary', params={"day": day or self.yesterday})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def review(self, day=None, status="complete", **overrides):
        day = day or self.yesterday
        payload = {"status": status, "fingerprint": self.diary(day)["fingerprint"]}
        payload.update(overrides)
        return self.client.put(
            f'/me/diary-records/{day}/review', params={"today": self.today}, json=payload
        )

    def approximation(self, **overrides):
        payload = {
            "entry_date": str(self.yesterday), "meal_type": "lunch", "name": "Refeicao de teste",
            "portions": 1.5, "kcal_per_portion": 600, "reference": "Cardapio de teste",
        }
        payload.update(overrides)
        return self.client.post('/me/diary-records/estimates', params={"today": self.today}, json=payload)

    def adaptive(self):
        response = self.client.get('/me/summary/adaptive', params={"day": self.today, "tz_offset": -120})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def populate_window(self):
        for offset in range(21):
            day = self.today - timedelta(days=offset)
            self.session.add(WeightLog(user_id=self.user.id, weight_kg=70, logged_at=datetime.combine(day, datetime.min.time()) + timedelta(hours=10)))
            if offset:
                self.entry(day)
        self.session.commit()

    def test_known_energy_is_added_without_inventing_macros(self):
        self.entry(self.yesterday, 1000)
        response = self.approximation()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["kcal"], 900)
        diary = self.diary()
        self.assertEqual(diary["totals"]["kcal"], 1900)
        self.assertEqual(diary["totals"]["protein_g"], 100)
        self.assertTrue(diary["review"]["has_unknown_macros"])
        self.assertFalse(diary["review"]["has_unknown_energy"])
        gap = self.client.get('/me/diary/gap', params={"day": self.yesterday}).json()
        self.assertEqual(gap["suggestions"], [])
        self.assertIsNone(gap["remaining"])

    def test_unknown_energy_stays_null_and_blocks_confirmation(self):
        response = self.approximation(kcal_per_portion=None, reference=None)
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["kcal"])
        self.assertTrue(self.diary()["review"]["has_unknown_energy"])
        response = self.review()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "DIARY_UNKNOWN_ENERGY")
        day = next(day for day in self.adaptive()["diary_days"] if day["date"] == str(self.yesterday))
        self.assertTrue(day["has_unknown_energy"])
        self.assertIsNone(day["kcal"])

    def test_empty_day_requires_explicit_no_consumption(self):
        self.assertEqual(self.review().status_code, 400)
        self.assertEqual(self.review(consumed_nothing=True).status_code, 200)
        self.assertEqual(self.diary()["review"]["status"], "complete")

    def test_content_change_invalidates_review_and_rejects_stale_form(self):
        entry = self.entry(self.yesterday)
        previous = self.diary()["fingerprint"]
        self.assertEqual(self.review().status_code, 200)
        entry.quantity = 150
        self.session.add(entry)
        self.session.commit()
        self.assertEqual(self.diary()["review"]["status"], "unreviewed")
        self.assertEqual(self.review(fingerprint=previous).status_code, 409)

    def test_copying_legacy_meal_invalidates_review_without_copying_approximations(self):
        self.entry(self.yesterday)
        source_day = self.today - timedelta(days=2)
        self.entry(source_day, 500)
        self.assertEqual(self.approximation(entry_date=str(source_day)).status_code, 201)
        self.assertEqual(self.review().status_code, 200)
        response = self.client.post('/me/diary/copy-previous', params={
            "day": self.yesterday, "from_day": source_day, "meal_type": "lunch",
        })
        self.assertEqual(response.status_code, 200, response.text)
        diary = response.json()
        self.assertEqual(diary["review"]["status"], "unreviewed")
        self.assertEqual(diary["totals"]["kcal"], 2500)
        self.assertEqual(diary["estimates"], [])

    def test_accepting_shared_meal_keeps_sender_and_invalidates_review(self):
        self.entry(self.yesterday)
        self.assertEqual(self.review().status_code, 200)
        sender = User(email="sender-tracking-test@example.invalid", password_hash="test-only")
        self.session.add(sender)
        self.session.flush()
        food = Food(slug="tracking-shared-food", category="cereal_grain", user_id=sender.id,
                    kcal=100, protein_g=2, carbs_g=20, fat_g=1)
        self.session.add(food)
        self.session.flush()
        offer = ShareOffer(from_user_id=sender.id, to_user_id=self.user.id, item_kind="meal",
                           item_name="lunch", meal_date=self.yesterday, meal_type="lunch")
        self.session.add(offer)
        self.session.flush()
        self.session.add(ShareOfferMealItem(offer_id=offer.id, source="food", food_id=food.id, quantity=100, kcal=100))
        self.session.commit()
        response = self.client.post(f'/me/sharing/offers/{offer.id}/accept')
        self.assertEqual(response.status_code, 200, response.text)
        diary = self.diary()
        self.assertEqual(diary["review"]["status"], "unreviewed")
        self.assertEqual(diary["totals"]["kcal"], 2100)
        entries = [entry for meal in diary["meals"] for entry in meal["entries"]]
        self.assertTrue(any(entry["received_from"] for entry in entries))

    def test_deleting_estimate_invalidates_day_review(self):
        self.entry(self.yesterday)
        response = self.approximation()
        estimate_id = response.json()["id"]
        self.assertEqual(self.review().status_code, 200)
        response = self.client.delete(f'/me/diary-records/estimates/{estimate_id}')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.diary()["review"]["status"], "unreviewed")

    def test_estimate_edit_recalculates_portions_and_invalidates_review(self):
        estimate_id = self.approximation().json()["id"]
        self.assertEqual(self.review().status_code, 200)
        response = self.client.put(f'/me/diary-records/estimates/{estimate_id}', params={"today": self.today}, json={
            "entry_date": str(self.yesterday), "meal_type": "dinner", "name": "Refeicao revisada",
            "portions": 2, "kcal_per_portion": 600, "reference": "Cardapio revisado",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kcal"], 1200)
        self.assertEqual(self.diary()["review"]["status"], "unreviewed")

    def test_owner_isolation_and_future_dates(self):
        estimate_id = self.approximation().json()["id"]
        other_user = User(email="other-tracking-test@example.invalid", password_hash="test-only")
        self.session.add(other_user)
        self.session.commit()
        app.dependency_overrides[get_current_user] = lambda: other_user
        self.assertEqual(self.client.delete(f'/me/diary-records/estimates/{estimate_id}').status_code, 404)
        self.assertEqual(self.diary()["estimates"], [])
        response = self.approximation(entry_date=str(self.today + timedelta(days=1)))
        self.assertEqual(response.status_code, 400)

    def test_adoption_requires_reviewed_window_and_is_checked_by_server(self):
        self.populate_window()
        before = self.adaptive()
        self.assertTrue(before["has_enough_data"])
        self.assertFalse(before["can_adopt"])
        self.assertEqual(before["message_code"], "REVIEW_DIARY")
        self.assertEqual(before["days_to_review"], 20)
        response = self.client.post('/me/diet/period/renew', params={
            "day": self.today, "tz_offset": -120, "adopt_maintenance_kcal": 2000,
        })
        self.assertEqual(response.status_code, 409)
        for offset in range(1, 21):
            self.assertEqual(self.review(self.today - timedelta(days=offset)).status_code, 200)
        after = self.adaptive()
        self.assertTrue(after["can_adopt"])
        self.assertEqual(after["days_to_review"], 0)
        response = self.client.post('/me/diet/period/renew', params={
            "day": self.today, "tz_offset": -120, "adopt_maintenance_kcal": 2000,
        })
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post('/me/diet/period/renew', params={
            "day": self.today, "adopt_maintenance_kcal": 2400,
        })
        self.assertEqual(response.status_code, 409)

    def test_low_confirmed_day_counts_and_today_food_does_not(self):
        self.populate_window()
        day = self.today - timedelta(days=2)
        entries = self.session.exec(text('SELECT id FROM diary_entries WHERE user_id = :user_id AND entry_date = :day').bindparams(user_id=self.user.id, day=day)).all()
        entry = self.session.get(DiaryEntry, entries[0][0])
        entry.kcal = 400
        self.session.add(entry)
        self.session.commit()
        before = self.adaptive()
        self.assertEqual(before["days_discarded"], 1)
        self.assertEqual(self.review(day).status_code, 200)
        self.entry(self.today, 9999)
        after = self.adaptive()
        self.assertEqual(after["days_discarded"], 0)
        self.assertEqual(after["days_logged"], 20)
        # Media = 19 dias de 2000 e um dia confirmado de 400, sem o dia de hoje.
        self.assertEqual(after["avg_intake_kcal"], 1920)

    def test_below_basal_stays_blocked_even_after_all_reviews(self):
        self.populate_window()
        self.session.exec(text('UPDATE diary_entries SET kcal = 900 WHERE user_id = :user_id').bindparams(user_id=self.user.id))
        self.session.commit()
        for offset in range(1, 21):
            self.assertEqual(self.review(self.today - timedelta(days=offset)).status_code, 200)
        result = self.adaptive()
        self.assertEqual(result["message_code"], "MEASURED_BELOW_BMR")
        self.assertFalse(result["can_adopt"])


if __name__ == '__main__':
    unittest.main()
