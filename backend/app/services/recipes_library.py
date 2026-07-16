"""Biblioteca de receitas semente (fase 2 da 'nutricionista particular').

As receitas vivem em seed_recipes.json (codigo, nao banco): cada uma referencia
ingredientes do catalogo por slug e os macros sao CALCULADOS dos ingredientes na
hora - nunca inventados. 'Adotar' copia a receita para as receitas do usuario
(modelo Recipe existente), onde ele pode editar e lancar no diario normalmente.
"""

import json
from pathlib import Path

from sqlmodel import Session, select

from ..models import Food, Recipe, RecipeIngredient, User
from ..schemas import LibraryIngredientOut, LibraryRecipeOut, MacrosOut
from .diet import food_macros, localized_food_name

SEED_RECIPES_FILE = Path(__file__).resolve().parent.parent / "seed_recipes.json"

_cache: list[dict] | None = None


def _load() -> list[dict]:
    global _cache
    if _cache is None:
        _cache = json.loads(SEED_RECIPES_FILE.read_text(encoding="utf-8"))
    return _cache


def _localized_recipe_name(entry: dict, locale: str) -> str:
    names = entry["names"]
    return names.get(locale) or names.get("en") or next(iter(names.values()))


def _global_foods_by_slug(session: Session) -> dict[str, Food]:
    foods = session.exec(select(Food).where(Food.user_id.is_(None))).all()
    return {f.slug: f for f in foods}


def _round1(value: float) -> float:
    return round(value, 1)


def _build_out(entry: dict, foods: dict[str, Food], locale: str) -> LibraryRecipeOut | None:
    ingredients: list[LibraryIngredientOut] = []
    total = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for ing in entry["ingredients"]:
        food = foods.get(ing["food"])
        if food is None:
            return None  # catalogo sem o ingrediente: receita fica invisivel (nao quebra)
        macros = food_macros(food, ing["grams"])
        total["kcal"] += macros.kcal
        total["protein_g"] += macros.protein_g
        total["carbs_g"] += macros.carbs_g
        total["fat_g"] += macros.fat_g
        ingredients.append(
            LibraryIngredientOut(name=localized_food_name(food, locale), grams=ing["grams"])
        )
    servings = max(entry["servings"], 1)
    return LibraryRecipeOut(
        slug=entry["slug"],
        name=_localized_recipe_name(entry, locale),
        tags=entry["tags"],
        servings=entry["servings"],
        total=MacrosOut(**{k: _round1(v) for k, v in total.items()}),
        per_serving=MacrosOut(**{k: _round1(v / servings) for k, v in total.items()}),
        ingredients=ingredients,
    )


def list_library(session: Session, user: User, tag: str | None = None) -> list[LibraryRecipeOut]:
    foods = _global_foods_by_slug(session)
    out: list[LibraryRecipeOut] = []
    for entry in _load():
        if tag and tag not in entry["tags"]:
            continue
        built = _build_out(entry, foods, user.locale)
        if built is not None:
            out.append(built)
    out.sort(key=lambda item: item.name.lower())
    return out


def adopt(session: Session, user: User, slug: str) -> Recipe | None:
    """Copia a receita da biblioteca para as receitas do usuario (idempotente:
    se ja existir uma receita dele com o mesmo nome, devolve a existente)."""
    entry = next((e for e in _load() if e["slug"] == slug), None)
    if entry is None:
        return None
    foods = _global_foods_by_slug(session)
    if any(ing["food"] not in foods for ing in entry["ingredients"]):
        return None
    name = _localized_recipe_name(entry, user.locale)
    existing = session.exec(
        select(Recipe).where(Recipe.user_id == user.id).where(Recipe.name == name)
    ).first()
    if existing is not None:
        return existing
    recipe = Recipe(user_id=user.id, name=name, servings=entry["servings"])
    session.add(recipe)
    session.flush()
    for ing in entry["ingredients"]:
        session.add(
            RecipeIngredient(
                recipe_id=recipe.id, food_id=foods[ing["food"]].id, grams=ing["grams"]
            )
        )
    session.commit()
    session.refresh(recipe)
    return recipe
