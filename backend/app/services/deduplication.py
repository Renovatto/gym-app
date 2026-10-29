"""Identidade de conteudo para detectar e reaproveitar itens equivalentes."""

import hashlib
import json
from collections import defaultdict
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, select

from ..models import Food, Recipe, RecipeIngredient
from ..schemas import DuplicateGroupOut, DuplicateItemOut
from .diet import localized_food_name


def food_content_key(food: Food) -> str:
    """Identifica um alimento pelos dados nutricionais, sem depender do nome ou ID."""
    portions = sorted(
        (portion.label_key, round(portion.grams, 3)) for portion in food.portions
    )
    return _fingerprint(
        {
            "category": food.category.value,
            "kcal": round(food.kcal, 4),
            "protein_g": round(food.protein_g, 4),
            "carbs_g": round(food.carbs_g, 4),
            "fat_g": round(food.fat_g, 4),
            "default_portion_g": round(food.default_portion_g, 3),
            "portions": portions,
        }
    )


def recipe_content_key(session: Session, recipe: Recipe) -> str:
    """Compara receitas sem nome; ingrediente, quantidade e rendimento definem o conteudo."""
    ingredients: list[tuple[str, float]] = []
    for ingredient in recipe.ingredients:
        food = session.get(Food, ingredient.food_id)
        if food is None:
            # Ingrediente orfao nao pode ser confundido com outra receita valida.
            return _fingerprint({"recipe_id": recipe.id, "invalid": ingredient.id})
        ingredients.append((food_content_key(food), round(ingredient.grams, 3)))
    ingredients.sort()
    return _fingerprint({"servings": recipe.servings, "ingredients": ingredients})


def duplicate_groups(session: Session, user_id: int, locale: str) -> list[DuplicateGroupOut]:
    """Agrupa conteudo ativo repetido e devolve apenas grupos com algo do usuario."""
    groups: list[DuplicateGroupOut] = []
    foods_by_key: dict[str, list[Food]] = defaultdict(list)
    foods = session.exec(
        select(Food)
        .where((Food.user_id.is_(None)) | (Food.user_id == user_id))
        .where(Food.archived_at.is_(None))
    ).all()
    for food in foods:
        foods_by_key[food_content_key(food)].append(food)

    for matching_foods in foods_by_key.values():
        if len(matching_foods) < 2 or not any(food.user_id == user_id for food in matching_foods):
            continue
        groups.append(
            DuplicateGroupOut(
                item_kind="food",
                items=[
                    DuplicateItemOut(
                        id=food.id,
                        name=localized_food_name(food, locale),
                        is_custom=food.user_id is not None,
                    )
                    for food in sorted(matching_foods, key=lambda item: item.id)
                ],
            )
        )

    recipes_by_key: dict[str, list[Recipe]] = defaultdict(list)
    recipes = session.exec(
        select(Recipe)
        .where(Recipe.user_id == user_id)
        .where(Recipe.archived_at.is_(None))
    ).all()
    for recipe in recipes:
        recipes_by_key[recipe_content_key(session, recipe)].append(recipe)

    for matching_recipes in recipes_by_key.values():
        if len(matching_recipes) < 2:
            continue
        groups.append(
            DuplicateGroupOut(
                item_kind="recipe",
                items=[
                    DuplicateItemOut(id=recipe.id, name=recipe.name, is_custom=True)
                    for recipe in sorted(matching_recipes, key=lambda item: item.id)
                ],
            )
        )

    return groups


def lock_content(session: Session, user_id: int, item_kind: str, content_key: str) -> None:
    """Serializa aceptes equivalentes para que dos requests no creen copias simultaneas."""
    lock_input = f"{user_id}:{item_kind}:{content_key}".encode("utf-8")
    # O PostgreSQL recebe uma chave bigint assinada; o hash mantem a mesma chave
    # para o mesmo destinatario e conteudo, mesmo se os IDs de origem forem diferentes.
    lock_key = int.from_bytes(hashlib.sha256(lock_input).digest()[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})


def lock_share_acceptance(session: Session, user_id: int) -> None:
    """Serializes accepted shares per recipient before any recipe or food lock."""
    lock_input = f"share-recipient:{user_id}".encode("utf-8")
    lock_key = int.from_bytes(hashlib.sha256(lock_input).digest()[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})


def _fingerprint(content: dict[str, Any]) -> str:
    serialized = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
