"""Regressoes em PostgreSQL para lancamentos ate o proximo dia local."""

from datetime import date, datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from sqlmodel import Session, select

import test_diary_tracking
from app.deps import get_current_user, get_session
from app.main import app
from app.models import (
    Connection, ConnectionStatus, DiaryEntry, EntrySource, Food, MealType,
    Recipe, RecipeIngredient, ShareOffer, ShareOfferStatus, SharedItem, SharedItemKind, User, UserAchievement,
)
from app.routers.diet import _meal_history, forget_received_entry
from app.services.diary_dates import local_today
from app.services.recommend import _food_frequency, _meal_food_frequency


class DiaryTomorrowTests(unittest.TestCase):
    tearDown = test_diary_tracking.DiaryTrackingTests.tearDown
    entry = test_diary_tracking.DiaryTrackingTests.entry
    diary = test_diary_tracking.DiaryTrackingTests.diary
    review = test_diary_tracking.DiaryTrackingTests.review
    approximation = test_diary_tracking.DiaryTrackingTests.approximation
    populate_window = test_diary_tracking.DiaryTrackingTests.populate_window

    def setUp(self):
        test_diary_tracking.DiaryTrackingTests.setUp(self)
        self.today = date(2026, 10, 27)
        self.yesterday = self.today - timedelta(days=1)
        self.tomorrow = self.today + timedelta(days=1)
        self.later = self.today + timedelta(days=2)
        clock = patch('app.services.diary_dates.utcnow', return_value=datetime(
            2026, 10, 27, 12, tzinfo=timezone.utc,
        ))
        clock.start()
        self.addCleanup(clock.stop)
        self.food = Food(
            user_id=self.user.id, slug="tomorrow-test-food", category="cereal_grain",
            kcal=100, protein_g=5, carbs_g=15, fat_g=2,
        )
        self.session.add(self.food)
        self.session.commit()

    def create_entry(self, day, tz_offset=0):
        return self.client.post('/me/diary', params={"tz_offset": tz_offset}, json={
            "entry_date": str(day), "meal_type": "lunch", "source": "food",
            "food_id": self.food.id, "quantity": 100,
        })

    def entries_on(self, day):
        return self.session.exec(select(DiaryEntry).where(
            DiaryEntry.user_id == self.user.id, DiaryEntry.entry_date == day,
        )).all()

    def partner(self):
        partner = User(email="tomorrow-partner@example.invalid", password_hash="test-only")
        self.session.add(partner)
        self.session.flush()
        connection = Connection(
            requester_user_id=self.user.id, addressee_user_id=partner.id,
            status=ConnectionStatus.accepted,
        )
        self.session.add(connection)
        self.session.commit()
        return partner, connection

    def offer(self, day, connection):
        return self.client.post('/me/sharing/meal-offers', params={"tz_offset": 0}, json={
            "entry_date": str(day), "meal_type": "lunch", "connection_id": connection.id,
        })

    def test_create_allows_tomorrow_and_rejects_later_without_writing(self):
        for day in [self.yesterday, self.today, self.tomorrow]:
            response = self.create_entry(day)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(len(self.entries_on(day)), 1)
        response = self.create_entry(self.later)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()["detail"], "DIARY_DAY_LIMIT")
        self.assertEqual(self.entries_on(self.later), [])
        response = self.client.delete(f'/me/diary/{self.entries_on(self.tomorrow)[0].id}')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.entries_on(self.tomorrow), [])

    def test_server_utc_and_timezone_determine_limit(self):
        with patch('app.services.diary_dates.utcnow', return_value=datetime(
            2026, 10, 27, 0, 30, tzinfo=timezone.utc,
        )):
            self.assertEqual(local_today(720), date(2026, 10, 26))
            self.assertEqual(self.create_entry(self.today, 720).status_code, 201)
            self.assertEqual(self.create_entry(self.tomorrow, 720).status_code, 400)
        with patch('app.services.diary_dates.utcnow', return_value=datetime(
            2026, 10, 27, 23, 30, tzinfo=timezone.utc,
        )):
            self.assertEqual(local_today(-840), self.tomorrow)
            self.assertEqual(self.create_entry(self.later, -840).status_code, 201)
        self.assertEqual(self.create_entry(self.tomorrow, -841).status_code, 422)
        self.assertEqual(self.create_entry(self.tomorrow, 721).status_code, 422)

    def test_library_validates_before_adoption(self):
        recipe = Recipe(user_id=self.user.id, name="Receita de teste", servings=1)
        recipe.ingredients.append(RecipeIngredient(food_id=self.food.id, grams=100))
        self.session.add(recipe)
        self.session.commit()
        with patch('app.routers.diet.adopt_library_recipe', return_value=recipe) as adopt:
            payload = {"slug": "test", "entry_date": str(self.later), "meal_type": "lunch"}
            response = self.client.post('/me/diary/from-library', json=payload)
            self.assertEqual(response.status_code, 400, response.text)
            adopt.assert_not_called()
            payload["entry_date"] = str(self.tomorrow)
            response = self.client.post('/me/diary/from-library', json=payload)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(self.entries_on(self.tomorrow)[0].recipe_id, recipe.id)

    def test_copy_previous_validates_destination_and_preserves_original(self):
        self.create_entry(self.today)
        response = self.client.post('/me/diary/copy-previous', params={
            "day": self.tomorrow, "from_day": self.today, "meal_type": "lunch", "tz_offset": 0,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.entries_on(self.today)), 1)
        self.assertEqual(len(self.entries_on(self.tomorrow)), 1)
        response = self.client.post('/me/diary/copy-previous', params={
            "day": self.later, "from_day": self.today, "tz_offset": 0,
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.entries_on(self.later), [])

    def test_shared_tomorrow_meal_requires_recipient_local_limit(self):
        partner, connection = self.partner()
        self.create_entry(self.tomorrow)
        response = self.offer(self.tomorrow, connection)
        self.assertEqual(response.status_code, 201, response.text)
        offer_id = response.json()["id"]
        app.dependency_overrides[get_current_user] = lambda: partner
        with patch('app.services.diary_dates.utcnow', return_value=datetime(
            2026, 10, 27, 0, 30, tzinfo=timezone.utc,
        )):
            response = self.client.post(f'/me/sharing/offers/{offer_id}/accept', params={"tz_offset": 720})
            self.assertEqual(response.status_code, 400, response.text)
            self.assertEqual(self.session.get(ShareOffer, offer_id).status, ShareOfferStatus.pending)
        response = self.client.post(f'/me/sharing/offers/{offer_id}/accept', params={"tz_offset": 0})
        self.assertEqual(response.status_code, 200, response.text)
        received = self.session.exec(select(DiaryEntry).where(DiaryEntry.user_id == partner.id)).all()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].entry_date, self.tomorrow)
        self.assertEqual(len(self.entries_on(self.tomorrow)), 1)

    def test_sharing_rejects_existing_later_entry_before_creating_offer(self):
        _, connection = self.partner()
        self.entry(self.later)
        response = self.offer(self.later, connection)
        self.assertEqual(response.status_code, 400, response.text)
        offers = self.session.exec(select(ShareOffer).where(ShareOffer.from_user_id == self.user.id)).all()
        self.assertEqual(offers, [])

    def test_tomorrow_is_excluded_from_habits_and_recent_foods(self):
        self.create_entry(self.tomorrow)
        for selected_day in [self.today, self.tomorrow]:
            self.assertEqual(_food_frequency(self.session, self.user.id, selected_day), {})
            self.assertEqual(_meal_food_frequency(self.session, self.user.id, MealType.lunch, selected_day), {})
        self.assertEqual(_meal_history(self.session, self.user.id, MealType.lunch, EntrySource.food), [])
        for params in [{}, {"meal_type": "lunch"}]:
            response = self.client.get('/me/foods/recent', params=params)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), [])
        self.create_entry(self.today)
        self.assertEqual(_food_frequency(self.session, self.user.id, self.tomorrow), {self.food.id: 1})
        self.assertEqual(_meal_history(self.session, self.user.id, MealType.lunch, EntrySource.food), [self.food.id])

    def test_tomorrow_stays_visible_but_does_not_change_current_calculations(self):
        self.populate_window()
        endpoints = ['/me/summary/adaptive', '/me/summary/week', '/me/diet/adherence', '/me/diary/gap']
        params = {"day": self.today, "end": self.today, "tz_offset": 0}
        before = [self.client.get(endpoint, params=params).json() for endpoint in endpoints]
        response = self.create_entry(self.tomorrow)
        self.assertEqual(response.status_code, 201, response.text)
        after = [self.client.get(endpoint, params=params).json() for endpoint in endpoints]
        self.assertEqual(before, after)
        self.assertEqual(self.diary(self.tomorrow)["totals"]["kcal"], 100)
        self.assertEqual(self.review(self.tomorrow).status_code, 400)
        self.assertEqual(self.approximation(entry_date=str(self.tomorrow)).status_code, 400)

    def test_future_summary_queries_end_at_actual_local_today(self):
        self.populate_window()
        self.entry(self.today, kcal=9999)
        self.create_entry(self.tomorrow)
        for endpoint, date_parameter in [
            ('/me/summary/adaptive', 'day'),
            ('/me/summary/week', 'day'),
            ('/me/diet/adherence', 'end'),
        ]:
            with self.subTest(endpoint=endpoint):
                current = self.client.get(endpoint, params={date_parameter: self.today, "tz_offset": 0})
                future = self.client.get(endpoint, params={date_parameter: self.later, "tz_offset": 0})
                self.assertEqual(current.status_code, 200, current.text)
                self.assertEqual(future.status_code, 200, future.text)
                self.assertEqual(current.json(), future.json())

    def test_habit_timezone_keeps_actual_local_today_and_excludes_local_tomorrow(self):
        self.create_entry(self.today)
        self.create_entry(self.tomorrow)
        with patch('app.services.diary_dates.utcnow', return_value=datetime(
            2026, 10, 27, 0, 30, tzinfo=timezone.utc,
        )):
            self.assertEqual(_food_frequency(self.session, self.user.id, self.tomorrow, 720), {})
            response = self.client.get('/me/foods/recent', params={"tz_offset": 720})
            self.assertEqual(response.json(), [])
        with patch('app.services.diary_dates.utcnow', return_value=datetime(
            2026, 10, 27, 23, 30, tzinfo=timezone.utc,
        )):
            self.assertEqual(_food_frequency(self.session, self.user.id, self.tomorrow, -840), {self.food.id: 2})
            self.assertEqual(_meal_food_frequency(
                self.session, self.user.id, MealType.lunch, self.tomorrow, -840,
            ), {self.food.id: 2})

    def test_food_sharing_does_not_require_diary_date(self):
        partner, connection = self.partner()
        response = self.client.post('/me/sharing/offers', json={
            "connection_id": connection.id,
            "items": [{"item_kind": "food", "item_id": self.food.id}],
        })
        self.assertEqual(response.status_code, 201, response.text)
        offer_id = response.json()[0]["id"]
        app.dependency_overrides[get_current_user] = lambda: partner
        response = self.client.post(f'/me/sharing/offers/{offer_id}/accept')
        self.assertEqual(response.status_code, 200, response.text)

    def test_adherence_clamp_uses_local_today_after_utc_midnight_boundary(self):
        self.populate_window()
        goals = self.diary(self.today)["goals"]
        completed_yesterday = self.entry(self.today, kcal=goals["kcal"])
        completed_yesterday.protein_g = goals["protein_g"]
        self.session.add(completed_yesterday)
        self.session.commit()
        self.entry(self.tomorrow, kcal=9999)
        self.entry(self.later, kcal=9999)
        with patch('app.services.diary_dates.utcnow', return_value=datetime(
            2026, 10, 27, 23, 30, tzinfo=timezone.utc,
        )):
            for tz_offset in [-120, -840]:
                with self.subTest(tz_offset=tz_offset):
                    current = self.client.get('/me/diet/adherence', params={
                        "end": self.tomorrow, "tz_offset": tz_offset, "window": 1,
                    })
                    future = self.client.get('/me/diet/adherence', params={
                        "end": self.later, "tz_offset": tz_offset, "window": 1,
                    })
                    self.assertEqual(current.status_code, 200, current.text)
                    self.assertEqual(future.status_code, 200, future.text)
                    self.assertEqual(current.json(), future.json())
                    self.assertEqual(current.json()["logged_days"], 1)
                    self.assertEqual(current.json()["kcal_pct"], 100)
                    self.assertEqual(current.json()["protein_pct"], 100)

    def test_future_entries_do_not_unlock_or_increment_diet_achievements(self):
        self.create_entry(self.tomorrow)

        def achievements():
            response = self.client.get('/me/achievements', params={
                "day": self.tomorrow, "tz_offset": 0,
            })
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            by_code = {item["code"]: item for item in result["achievements"]}
            mission = next(item for item in result["weekly_missions"] if item["code"] == "diet")
            return by_code, mission

        by_code, mission = achievements()
        self.assertFalse(by_code["first_diet_log"]["unlocked"])
        self.assertEqual(by_code["first_diet_log"]["progress_current"], 0)
        self.assertEqual(mission["current"], 0)
        records = self.session.exec(select(UserAchievement).where(UserAchievement.user_id == self.user.id)).all()
        self.assertEqual(records, [])
        for offset in range(1, 7):
            self.entry(self.today - timedelta(days=offset))
        by_code, mission = achievements()
        self.assertTrue(by_code["first_diet_log"]["unlocked"])
        self.assertFalse(by_code["diet_days_7"]["unlocked"])
        self.assertEqual(by_code["diet_days_7"]["progress_current"], 6)
        # A semana comeca na segunda: so ontem, dia 26, conta ate esta terca-feira.
        self.assertEqual(mission["current"], 1)
        self.assertIsNone(self.session.exec(select(UserAchievement).where(
            UserAchievement.user_id == self.user.id, UserAchievement.code == "diet_days_7",
        )).first())
        self.entry(self.today)
        by_code, mission = achievements()
        self.assertTrue(by_code["diet_days_7"]["unlocked"])
        self.assertEqual(by_code["diet_days_7"]["progress_current"], 7)
        self.assertEqual(mission["current"], 2)

    def test_cycle_suggestions_keep_history_from_actual_local_today(self):
        self.populate_window()
        self.create_entry(self.tomorrow)
        with patch('app.services.diary_dates.utcnow', return_value=datetime(
            2026, 10, 27, 23, 30, tzinfo=timezone.utc,
        )), patch('app.services.recommend.phase_boost_food_ids', return_value={self.food.id}), patch(
            'app.services.recommend._rank_suggestions', return_value=[],
        ) as rank:
            self.create_entry(self.later, tz_offset=-120)
            params = {"day": self.tomorrow, "tz_offset": -120}
            response = self.client.put('/me/cycle', params=params, json={
                "enabled": True, "mode": "manual", "phase": "menstrual",
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(rank.call_args.args[4], {self.food.id: 1})
            rank.reset_mock()
            response = self.client.get('/me/cycle', params=params)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(rank.call_args.args[4], {self.food.id: 1})

    def test_undo_additions_removes_only_captured_group_and_received_links(self):
        captured_ids = [self.create_entry(self.tomorrow).json()["id"] for _ in range(2)]
        unrelated_id = self.create_entry(self.tomorrow).json()["id"]
        past_entry = self.entry(self.yesterday)
        sender, _ = self.partner()
        for entry_id in [*captured_ids, unrelated_id]:
            self.session.add(SharedItem(
                owner_user_id=self.user.id, item_kind=SharedItemKind.diary_entry,
                item_id=entry_id, source_item_id=entry_id, from_user_id=sender.id,
            ))
        self.session.commit()
        response = self.client.post('/me/diary/undo-additions', json={
            "entry_ids": [*captured_ids, captured_ids[0]],
        })
        self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(response.content, b"")
        for entry_id in captured_ids:
            self.assertIsNone(self.session.get(DiaryEntry, entry_id))
        self.assertIsNotNone(self.session.get(DiaryEntry, unrelated_id))
        self.assertIsNotNone(self.session.get(DiaryEntry, past_entry.id))
        received_ids = self.session.exec(select(SharedItem.item_id).where(
            SharedItem.owner_user_id == self.user.id,
            SharedItem.item_kind == SharedItemKind.diary_entry,
        )).all()
        self.assertEqual(received_ids, [unrelated_id])

    def test_undo_additions_rejects_other_owner_before_removing_any_entry(self):
        own_ids = [self.create_entry(self.tomorrow).json()["id"] for _ in range(2)]
        other_user, _ = self.partner()
        foreign_entry = self.entry(self.tomorrow)
        foreign_entry.user_id = other_user.id
        self.session.add(foreign_entry)
        self.session.add(SharedItem(
            owner_user_id=self.user.id, item_kind=SharedItemKind.diary_entry,
            item_id=own_ids[0], source_item_id=foreign_entry.id, from_user_id=other_user.id,
        ))
        self.session.commit()
        response = self.client.post('/me/diary/undo-additions', json={
            "entry_ids": [*own_ids, foreign_entry.id],
        })
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json()["detail"], "ENTRY_NOT_FOUND")
        for entry_id in [*own_ids, foreign_entry.id]:
            self.assertIsNotNone(self.session.get(DiaryEntry, entry_id))
        self.assertIsNotNone(self.session.exec(select(SharedItem).where(
            SharedItem.owner_user_id == self.user.id,
            SharedItem.item_id == own_ids[0],
        )).first())

    def test_undo_additions_is_idempotent_after_manual_removal_and_response_loss(self):
        captured_ids = [self.create_entry(self.tomorrow).json()["id"] for _ in range(2)]
        unrelated_id = self.create_entry(self.tomorrow).json()["id"]
        response = self.client.delete(f'/me/diary/{captured_ids[0]}')
        self.assertEqual(response.status_code, 204, response.text)
        for _ in range(2):
            response = self.client.post('/me/diary/undo-additions', json={"entry_ids": captured_ids})
            self.assertEqual(response.status_code, 204, response.text)
            for entry_id in captured_ids:
                self.assertIsNone(self.session.get(DiaryEntry, entry_id))
            self.assertIsNotNone(self.session.get(DiaryEntry, unrelated_id))

    def test_undo_additions_failure_rolls_back_entire_group(self):
        captured_ids = [self.create_entry(self.tomorrow).json()["id"] for _ in range(2)]

        def request_session():
            # Como get_session em producao: fechar a sessao desfaz uma falha no pedido.
            with Session(bind=self.connection, join_transaction_mode="create_savepoint") as session:
                yield session

        app.dependency_overrides[get_session] = request_session
        processed_ids = []

        def fail_on_second_entry(session, user_id, entry_id):
            processed_ids.append(entry_id)
            if len(processed_ids) == 2:
                raise RuntimeError("Falha de teste no segundo item")
            forget_received_entry(session, user_id, entry_id)

        with patch('app.routers.diet.forget_received_entry', side_effect=fail_on_second_entry):
            with self.assertRaisesRegex(RuntimeError, "Falha de teste no segundo item"):
                self.client.post('/me/diary/undo-additions', json={"entry_ids": captured_ids})
        self.assertEqual(processed_ids, captured_ids)
        self.session.expire_all()
        for entry_id in captured_ids:
            self.assertIsNotNone(self.session.get(DiaryEntry, entry_id))
