"""Testes PostgreSQL de deduplicacao de itens compartilhados e arquivamento."""

from datetime import date
from threading import Barrier, Event, Thread
from time import sleep
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.deps import get_current_user, get_session
from app.main import app
from app.models import (
    Food,
    FoodCategory,
    FoodTranslation,
    DiaryEntry,
    MealType,
    Recipe,
    RecipeIngredient,
    ShareOffer,
    ShareOfferStatus,
    SharedItem,
    SharedItemKind,
    User,
)
from app.services.deduplication import lock_share_acceptance
from app.services.recommend import _visible_foods
from app.services.recipes_library import adopt


class SharingDeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.sender = User(email="sharing-dedup-sender@example.invalid", password_hash="test-only")
        self.receiver = User(email="sharing-dedup-receiver@example.invalid", password_hash="test-only")
        self.session.add_all([self.sender, self.receiver])
        self.session.flush()
        app.dependency_overrides[get_session] = lambda: self.session
        app.dependency_overrides[get_current_user] = lambda: self.receiver
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def food(self, name: str, kcal: float = 100, owner_id: int | None = None) -> Food:
        food = Food(
            slug=f"sharing-dedup-{self.sender.id}-{name.lower().replace(' ', '-')}",
            category=FoodCategory.cereal_grain,
            kcal=kcal,
            protein_g=4,
            carbs_g=20,
            fat_g=2,
            default_portion_g=100,
            user_id=owner_id or self.sender.id,
        )
        self.session.add(food)
        self.session.flush()
        self.session.add(FoodTranslation(food_id=food.id, locale="pt-BR", name=name))
        self.session.flush()
        return food

    def recipe(
        self, name: str, ingredients: list[tuple[Food, float]], owner_id: int | None = None
    ) -> Recipe:
        recipe = Recipe(user_id=owner_id or self.sender.id, name=name, servings=1)
        self.session.add(recipe)
        self.session.flush()
        for food, grams in ingredients:
            self.session.add(RecipeIngredient(recipe_id=recipe.id, food_id=food.id, grams=grams))
        self.session.flush()
        return recipe

    def offer(self, item_kind: SharedItemKind, item_id: int) -> ShareOffer:
        offer = ShareOffer(
            from_user_id=self.sender.id,
            to_user_id=self.receiver.id,
            item_kind=item_kind,
            item_id=item_id,
            item_name="Item de teste",
        )
        self.session.add(offer)
        self.session.commit()
        return offer

    def accept(self, offer: ShareOffer) -> dict:
        response = self.client.post(f"/me/sharing/offers/{offer.id}/accept")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_edited_recipe_is_received_as_a_new_content_version(self):
        rice = self.food("Arroz de teste")
        source = self.recipe("Receita original", [(rice, 100)])
        first_offer = self.offer(SharedItemKind.recipe, source.id)
        first_copy_id = self.accept(first_offer)["item_id"]

        source.ingredients[0].grams = 220
        self.session.add(source.ingredients[0])
        self.session.commit()

        second_offer = self.offer(SharedItemKind.recipe, source.id)
        second_copy_id = self.accept(second_offer)["item_id"]

        self.assertNotEqual(first_copy_id, second_copy_id)
        second_copy = self.session.get(Recipe, second_copy_id)
        self.assertEqual(second_copy.ingredients[0].grams, 220)
        received_versions = self.session.exec(
            select(SharedItem).where(
                SharedItem.owner_user_id == self.receiver.id,
                SharedItem.item_kind == SharedItemKind.recipe,
                SharedItem.source_item_id == source.id,
                SharedItem.from_user_id == self.sender.id,
            )
        ).all()
        self.assertEqual(len(received_versions), 2)

    def test_same_recipe_content_with_different_ids_and_names_is_reused(self):
        first_food = self.food("Aveia nome A")
        second_food = self.food("Aveia nome B")
        first_recipe = self.recipe("Mingau", [(first_food, 80)])
        second_recipe = self.recipe("Creme de aveia", [(second_food, 80)])

        first_copy_id = self.accept(self.offer(SharedItemKind.recipe, first_recipe.id))["item_id"]
        second_copy_id = self.accept(self.offer(SharedItemKind.recipe, second_recipe.id))["item_id"]

        self.assertEqual(first_copy_id, second_copy_id)
        receiver_recipes = self.session.exec(
            select(Recipe).where(Recipe.user_id == self.receiver.id)
        ).all()
        self.assertEqual(len(receiver_recipes), 1)
        received = self.client.get("/me/sharing/received")
        self.assertEqual(received.status_code, 200, received.text)
        matching_received = [item for item in received.json() if item["item_id"] == first_copy_id]
        self.assertEqual(len(matching_received), 1)

    def test_edited_personal_food_is_received_as_a_new_content_version(self):
        source = self.food("Iogurte de teste")
        first_copy_id = self.accept(self.offer(SharedItemKind.food, source.id))["item_id"]

        source.kcal = 145
        self.session.add(source)
        self.session.commit()

        second_copy_id = self.accept(self.offer(SharedItemKind.food, source.id))["item_id"]

        self.assertNotEqual(first_copy_id, second_copy_id)
        self.assertEqual(self.session.get(Food, second_copy_id).kcal, 145)

    def test_duplicate_groups_ignore_names_and_archive_hides_items(self):
        first_food = self.food("Iogurte A", owner_id=self.receiver.id)
        second_food = self.food("Iogurte B", owner_id=self.receiver.id)
        first_recipe = self.recipe("Receita A", [(first_food, 100)], owner_id=self.receiver.id)
        second_recipe = self.recipe("Receita B", [(second_food, 100)], owner_id=self.receiver.id)
        self.session.commit()

        groups = self.client.get("/me/diet/duplicates")
        self.assertEqual(groups.status_code, 200, groups.text)
        grouped_kinds = {group["item_kind"] for group in groups.json()}
        self.assertEqual(grouped_kinds, {"food", "recipe"})

        archived = self.client.post(f"/me/recipes/{second_recipe.id}/archive")
        self.assertEqual(archived.status_code, 200, archived.text)
        active_recipes = self.client.get("/me/recipes").json()
        archived_recipes = self.client.get("/me/recipes?include_archived=true").json()
        self.assertNotIn(second_recipe.id, {recipe["id"] for recipe in active_recipes})
        self.assertIn(second_recipe.id, {recipe["id"] for recipe in archived_recipes})

        remaining_groups = self.client.get("/me/diet/duplicates").json()
        self.assertFalse(any(group["item_kind"] == "recipe" for group in remaining_groups))
        restored = self.client.post(f"/me/recipes/{second_recipe.id}/unarchive")
        self.assertEqual(restored.status_code, 200, restored.text)

        food_archived = self.client.post(f"/me/foods/{second_food.id}/archive")
        self.assertEqual(food_archived.status_code, 200, food_archived.text)
        visible_foods = self.client.get("/foods?scope=mine&limit=200").json()
        archived_foods = self.client.get(
            "/foods?scope=mine&include_archived=true&limit=200"
        ).json()
        self.assertNotIn(second_food.id, {food["id"] for food in visible_foods})
        self.assertNotIn(second_food.id, {food.id for food in _visible_foods(self.session, self.receiver.id)})
        updated_existing_recipe = self.client.put(
            f"/me/recipes/{second_recipe.id}",
            json={
                "name": second_recipe.name,
                "servings": second_recipe.servings,
                "ingredients": [{"food_id": second_food.id, "grams": 100}],
            },
        )
        self.assertEqual(updated_existing_recipe.status_code, 200, updated_existing_recipe.text)
        rejected_new_recipe = self.client.post(
            "/me/recipes",
            json={
                "name": "Receita nova com alimento inativo",
                "servings": 1,
                "ingredients": [{"food_id": second_food.id, "grams": 100}],
            },
        )
        self.assertEqual(rejected_new_recipe.status_code, 400)
        self.assertIn(second_food.id, {food["id"] for food in archived_foods})
        self.assertIsNotNone(archived_foods[[food["id"] for food in archived_foods].index(second_food.id)]["archived_at"])
        restored_food = self.client.post(f"/me/foods/{second_food.id}/unarchive")
        self.assertEqual(restored_food.status_code, 200, restored_food.text)
        restored_groups = self.client.get("/me/diet/duplicates").json()
        self.assertTrue(any(group["item_kind"] == "food" for group in restored_groups))

    def test_editing_recipe_does_not_recalculate_existing_diary_entries(self):
        rice = self.food("Arroz do diario", owner_id=self.receiver.id)
        recipe = self.recipe("Receita do diario", [(rice, 100)], owner_id=self.receiver.id)
        entry_day = date.today()
        logged = self.client.post(
            "/me/diary",
            params={"tz_offset": 0},
            json={
                "entry_date": entry_day.isoformat(),
                "meal_type": "lunch",
                "source": "recipe",
                "recipe_id": recipe.id,
                "quantity": 1,
            },
        )
        self.assertEqual(logged.status_code, 201, logged.text)
        self.assertEqual(logged.json()["macros"]["kcal"], 100)
        self.session.get(DiaryEntry, logged.json()["id"]).grams = None
        self.session.commit()

        edited = self.client.put(
            f"/me/recipes/{recipe.id}",
            json={
                "name": recipe.name,
                "servings": recipe.servings,
                "ingredients": [{"food_id": rice.id, "grams": 220}],
            },
        )
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["per_serving"]["kcal"], 220)

        diary = self.client.get("/me/diary", params={"day": entry_day.isoformat()})
        self.assertEqual(diary.status_code, 200, diary.text)
        lunch_entries = next(
            meal["entries"] for meal in diary.json()["meals"] if meal["meal_type"] == "lunch"
        )
        self.assertEqual(lunch_entries[0]["macros"]["kcal"], 100)
        self.assertIsNone(lunch_entries[0]["grams"])
        self.assertEqual(diary.json()["totals"]["kcal"], 100)

    def test_library_adoption_does_not_return_archived_same_name_recipe(self):
        catalog_food = Food(
            slug=f"sharing-dedup-library-{self.receiver.id}",
            category=FoodCategory.cereal_grain,
            kcal=100,
            protein_g=4,
            carbs_g=20,
            fat_g=2,
            default_portion_g=100,
        )
        self.session.add(catalog_food)
        self.session.flush()
        archived_recipe = self.recipe(
            "Receita da biblioteca", [(catalog_food, 100)], owner_id=self.receiver.id
        )
        archived_recipe.archived_at = archived_recipe.created_at
        self.session.commit()
        library_entry = {
            "slug": "test-library-recipe",
            "names": {"pt-BR": "Receita da biblioteca"},
            "tags": [],
            "servings": 1,
            "ingredients": [{"food": catalog_food.slug, "grams": 100}],
        }

        with patch("app.services.recipes_library._load", return_value=[library_entry]):
            adopted = adopt(self.session, self.receiver, "test-library-recipe")

        self.assertIsNotNone(adopted)
        self.assertNotEqual(adopted.id, archived_recipe.id)
        self.assertIsNone(adopted.archived_at)

    def test_share_acceptance_lock_serializes_same_recipient(self):
        first_connection = engine.connect()
        first_transaction = first_connection.begin()
        first_session = Session(bind=first_connection)
        second_started = Event()
        second_acquired = Event()

        def acquire_second_lock():
            with engine.connect() as second_connection:
                with Session(bind=second_connection) as second_session:
                    with second_connection.begin():
                        second_started.set()
                        lock_share_acceptance(second_session, self.receiver.id)
                        second_acquired.set()

        try:
            lock_share_acceptance(first_session, self.receiver.id)
            worker = Thread(target=acquire_second_lock)
            worker.start()
            self.assertTrue(second_started.wait(timeout=2))
            self.assertFalse(second_acquired.wait(timeout=0.1))
            first_transaction.commit()
            self.assertTrue(second_acquired.wait(timeout=2))
            worker.join(timeout=2)
        finally:
            if first_transaction.is_active:
                first_transaction.rollback()
            first_session.close()
            first_connection.close()

    def test_concurrent_acceptance_of_one_meal_offer_only_accepts_once(self):
        unique_suffix = uuid4().hex
        committed_sender = User(
            email=f"concurrent-sender-{unique_suffix}@example.invalid", password_hash="test-only"
        )
        committed_receiver = User(
            email=f"concurrent-receiver-{unique_suffix}@example.invalid", password_hash="test-only"
        )
        with Session(engine) as setup_session:
            setup_session.add_all([committed_sender, committed_receiver])
            setup_session.flush()
            sender_id = committed_sender.id
            receiver_id = committed_receiver.id
            meal_offer = ShareOffer(
                from_user_id=committed_sender.id,
                to_user_id=receiver_id,
                item_kind=SharedItemKind.meal,
                item_name="lunch",
                meal_date=date.today(),
                meal_type=MealType.lunch,
            )
            setup_session.add(meal_offer)
            setup_session.commit()
            offer_id = meal_offer.id
        start_together = Barrier(2)
        outcomes: list[int] = []

        def accept_offer_concurrently():
            with engine.connect() as connection:
                with Session(bind=connection) as session:
                    with connection.begin():
                        start_together.wait(timeout=2)
                        lock_share_acceptance(session, receiver_id)
                        current_offer = session.get(ShareOffer, offer_id)
                        if current_offer.status != ShareOfferStatus.pending:
                            outcomes.append(409)
                            return
                        current_offer.status = ShareOfferStatus.accepted
                        session.add(current_offer)
                        session.flush()
                        sleep(0.05)
                        outcomes.append(200)

        workers = [Thread(target=accept_offer_concurrently) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=3)

        try:
            self.assertTrue(all(not worker.is_alive() for worker in workers))
            self.assertCountEqual(outcomes, [200, 409])
        finally:
            with Session(engine) as cleanup_session:
                cleanup_receiver = cleanup_session.get(User, receiver_id)
                cleanup_sender = cleanup_session.get(User, sender_id)
                if cleanup_receiver is not None:
                    cleanup_session.delete(cleanup_receiver)
                if cleanup_sender is not None:
                    cleanup_session.delete(cleanup_sender)
                cleanup_session.commit()


if __name__ == "__main__":
    unittest.main()
