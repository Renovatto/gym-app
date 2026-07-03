"""Helpers de dieta: localização de nome de alimento e cálculo de macros."""

from sqlmodel import Session

from ..models import Food, Recipe, RecipeIngredient
from ..schemas import FoodOut, FoodPortionOut, MacrosOut, RecipeIngredientOut

FALLBACK_LOCALE = "en"


def localized_food_name(food: Food, locale: str) -> str:
    translations = {t.locale: t.name for t in food.translations}
    return (
        translations.get(locale)
        or translations.get(FALLBACK_LOCALE)
        or next(iter(translations.values()), food.slug)
    )


def to_food_out(food: Food, locale: str) -> FoodOut:
    return FoodOut(
        id=food.id,
        slug=food.slug,
        name=localized_food_name(food, locale),
        category=food.category,
        kcal=food.kcal,
        protein_g=food.protein_g,
        carbs_g=food.carbs_g,
        fat_g=food.fat_g,
        default_portion_g=food.default_portion_g,
        portions=[FoodPortionOut(label_key=p.label_key, grams=p.grams) for p in food.portions],
        is_custom=food.user_id is not None,
    )


def _round(value: float) -> float:
    return round(value, 1)


def food_macros(food: Food, grams: float) -> MacrosOut:
    factor = grams / 100.0
    return MacrosOut(
        kcal=_round(food.kcal * factor),
        protein_g=_round(food.protein_g * factor),
        carbs_g=_round(food.carbs_g * factor),
        fat_g=_round(food.fat_g * factor),
    )


def _sum_macros(items: list[MacrosOut]) -> MacrosOut:
    return MacrosOut(
        kcal=_round(sum(m.kcal for m in items)),
        protein_g=_round(sum(m.protein_g for m in items)),
        carbs_g=_round(sum(m.carbs_g for m in items)),
        fat_g=_round(sum(m.fat_g for m in items)),
    )


def recipe_breakdown(
    session: Session, recipe: Recipe, locale: str
) -> tuple[list[RecipeIngredientOut], MacrosOut, MacrosOut]:
    ing_outs: list[RecipeIngredientOut] = []
    macros_list: list[MacrosOut] = []
    for ing in recipe.ingredients:
        food = session.get(Food, ing.food_id)
        if food is None:
            continue
        macros = food_macros(food, ing.grams)
        macros_list.append(macros)
        ing_outs.append(
            RecipeIngredientOut(
                id=ing.id, food=to_food_out(food, locale), grams=ing.grams, macros=macros
            )
        )
    total = _sum_macros(macros_list)
    servings = max(recipe.servings, 1)
    per_serving = MacrosOut(
        kcal=_round(total.kcal / servings),
        protein_g=_round(total.protein_g / servings),
        carbs_g=_round(total.carbs_g / servings),
        fat_g=_round(total.fat_g / servings),
    )
    return ing_outs, total, per_serving


def recipe_serving_macros(session: Session, recipe: Recipe) -> MacrosOut:
    _, total, per_serving = recipe_breakdown(session, recipe, FALLBACK_LOCALE)
    return per_serving


def sum_macros(items: list[MacrosOut]) -> MacrosOut:
    return _sum_macros(items)
