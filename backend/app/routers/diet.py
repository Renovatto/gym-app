from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, desc, select

from ..deps import CurrentUser, SessionDep
from ..models import (
    DiaryEntry,
    EntrySource,
    Food,
    FoodCategory,
    FoodTranslation,
    MealType,
    Profile,
    Recipe,
    RecipeIngredient,
    WeightLog,
)
from ..schemas import (
    DiaryDayOut,
    DiaryEntryIn,
    DiaryEntryOut,
    FoodIn,
    FoodOut,
    MacrosOut,
    MealGroupOut,
    RecipeIn,
    RecipeOut,
)
from ..services.diet import (
    food_macros,
    localized_food_name,
    recipe_breakdown,
    sum_macros,
    to_food_out,
)
from ..services.goals import compute_goals

router = APIRouter(tags=["diet"])


# --- Alimentos ------------------------------------------------------------


@router.get("/foods", response_model=list[FoodOut])
def list_foods(
    user: CurrentUser,
    session: SessionDep,
    q: str = Query(default="", max_length=60),
    category: FoodCategory | None = Query(default=None),
    limit: int = Query(default=60, ge=1, le=200),
) -> list[FoodOut]:
    query = select(Food).where((Food.user_id.is_(None)) | (Food.user_id == user.id))
    if category is not None:
        query = query.where(Food.category == category)
    foods = session.exec(query).all()

    term = q.strip().lower()
    out = []
    for food in foods:
        name = localized_food_name(food, user.locale)
        if term and term not in name.lower():
            # também busca em qualquer idioma cadastrado (ex.: nome em inglês)
            if not any(term in t.name.lower() for t in food.translations):
                continue
        out.append(to_food_out(food, user.locale))
    out.sort(key=lambda f: f.name.lower())
    return out[:limit]


@router.post("/me/foods", response_model=FoodOut, status_code=status.HTTP_201_CREATED)
def create_food(data: FoodIn, user: CurrentUser, session: SessionDep) -> FoodOut:
    slug = f"custom-{user.id}-{data.name.strip().lower().replace(' ', '-')}"
    food = Food(
        slug=slug,
        category=data.category,
        kcal=data.kcal,
        protein_g=data.protein_g,
        carbs_g=data.carbs_g,
        fat_g=data.fat_g,
        default_portion_g=data.default_portion_g,
        user_id=user.id,
    )
    session.add(food)
    session.flush()
    session.add(FoodTranslation(food_id=food.id, locale=user.locale, name=data.name.strip()))
    session.commit()
    session.refresh(food)
    return to_food_out(food, user.locale)


# --- Receitas -------------------------------------------------------------


def _visible_food(session: Session, food_id: int, user_id: int) -> Food | None:
    food = session.get(Food, food_id)
    if food is None or (food.user_id is not None and food.user_id != user_id):
        return None
    return food


def _recipe_out(session: Session, recipe: Recipe, locale: str) -> RecipeOut:
    ings, total, per_serving = recipe_breakdown(session, recipe, locale)
    return RecipeOut(
        id=recipe.id,
        name=recipe.name,
        servings=recipe.servings,
        ingredients=ings,
        total=total,
        per_serving=per_serving,
    )


@router.get("/me/recipes", response_model=list[RecipeOut])
def list_recipes(user: CurrentUser, session: SessionDep) -> list[RecipeOut]:
    recipes = session.exec(
        select(Recipe).where(Recipe.user_id == user.id).order_by(desc(Recipe.created_at))
    ).all()
    return [_recipe_out(session, r, user.locale) for r in recipes]


@router.post("/me/recipes", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
def create_recipe(data: RecipeIn, user: CurrentUser, session: SessionDep) -> RecipeOut:
    recipe = Recipe(user_id=user.id, name=data.name.strip(), servings=data.servings)
    session.add(recipe)
    session.flush()
    for ing in data.ingredients:
        if _visible_food(session, ing.food_id, user.id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="FOOD_NOT_FOUND")
        session.add(
            RecipeIngredient(recipe_id=recipe.id, food_id=ing.food_id, grams=ing.grams)
        )
    session.commit()
    session.refresh(recipe)
    return _recipe_out(session, recipe, user.locale)


def _get_owned_recipe(session: Session, recipe_id: int, user_id: int) -> Recipe:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="RECIPE_NOT_FOUND")
    return recipe


@router.put("/me/recipes/{recipe_id}", response_model=RecipeOut)
def update_recipe(
    recipe_id: int, data: RecipeIn, user: CurrentUser, session: SessionDep
) -> RecipeOut:
    recipe = _get_owned_recipe(session, recipe_id, user.id)
    recipe.name = data.name.strip()
    recipe.servings = data.servings
    # limpar pela coleção (delete-orphan) evita re-adicionar instâncias deletadas
    recipe.ingredients.clear()
    session.flush()
    for ing in data.ingredients:
        if _visible_food(session, ing.food_id, user.id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="FOOD_NOT_FOUND")
        session.add(RecipeIngredient(recipe_id=recipe.id, food_id=ing.food_id, grams=ing.grams))
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    return _recipe_out(session, recipe, user.locale)


@router.delete("/me/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(recipe_id: int, user: CurrentUser, session: SessionDep) -> None:
    recipe = _get_owned_recipe(session, recipe_id, user.id)
    session.delete(recipe)
    session.commit()


# --- Diário ---------------------------------------------------------------


def _daily_goals(session: Session, user_id: int) -> MacrosOut | None:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    latest = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user_id)
        .order_by(desc(WeightLog.logged_at), desc(WeightLog.id))
    ).first()
    if profile is None or latest is None:
        return None
    g = compute_goals(profile, latest.weight_kg)
    return MacrosOut(
        kcal=g.target_kcal, protein_g=g.protein_g, carbs_g=g.carbs_g, fat_g=g.fat_g
    )


def _entry_out(entry: DiaryEntry) -> DiaryEntryOut:
    return DiaryEntryOut(
        id=entry.id,
        meal_type=entry.meal_type,
        source=entry.source,
        food_id=entry.food_id,
        recipe_id=entry.recipe_id,
        name=entry.name_snapshot,
        quantity=entry.quantity,
        macros=MacrosOut(
            kcal=entry.kcal, protein_g=entry.protein_g, carbs_g=entry.carbs_g, fat_g=entry.fat_g
        ),
    )


@router.get("/me/diary", response_model=DiaryDayOut)
def get_diary(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (YYYY-MM-DD)"),
) -> DiaryDayOut:
    entries = session.exec(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user.id)
        .where(DiaryEntry.entry_date == day)
    ).all()
    meals: list[MealGroupOut] = []
    for meal_type in MealType:
        group = [e for e in entries if e.meal_type == meal_type]
        entry_outs = [_entry_out(e) for e in group]
        subtotal = sum_macros([e.macros for e in entry_outs])
        meals.append(MealGroupOut(meal_type=meal_type, entries=entry_outs, subtotal=subtotal))
    totals = sum_macros([_entry_out(e).macros for e in entries])
    return DiaryDayOut(date=day, meals=meals, totals=totals, goals=_daily_goals(session, user.id))


@router.post("/me/diary", response_model=DiaryEntryOut, status_code=status.HTTP_201_CREATED)
def add_diary_entry(data: DiaryEntryIn, user: CurrentUser, session: SessionDep) -> DiaryEntryOut:
    if data.source == EntrySource.food:
        if data.food_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="FOOD_REQUIRED")
        food = _visible_food(session, data.food_id, user.id)
        if food is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="FOOD_NOT_FOUND")
        macros = food_macros(food, data.quantity)
        name = localized_food_name(food, user.locale)
    else:
        if data.recipe_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="RECIPE_REQUIRED")
        recipe = _get_owned_recipe(session, data.recipe_id, user.id)
        _, _, per_serving = recipe_breakdown(session, recipe, user.locale)
        macros = MacrosOut(
            kcal=round(per_serving.kcal * data.quantity, 1),
            protein_g=round(per_serving.protein_g * data.quantity, 1),
            carbs_g=round(per_serving.carbs_g * data.quantity, 1),
            fat_g=round(per_serving.fat_g * data.quantity, 1),
        )
        name = recipe.name

    entry = DiaryEntry(
        user_id=user.id,
        entry_date=data.entry_date,
        meal_type=data.meal_type,
        source=data.source,
        food_id=data.food_id,
        recipe_id=data.recipe_id,
        quantity=data.quantity,
        name_snapshot=name,
        kcal=macros.kcal,
        protein_g=macros.protein_g,
        carbs_g=macros.carbs_g,
        fat_g=macros.fat_g,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return _entry_out(entry)


@router.delete("/me/diary/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diary_entry(entry_id: int, user: CurrentUser, session: SessionDep) -> None:
    entry = session.get(DiaryEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ENTRY_NOT_FOUND")
    session.delete(entry)
    session.commit()


@router.post("/me/diary/copy-previous", response_model=DiaryDayOut)
def copy_previous_day(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(...),
    from_day: date = Query(...),
    meal_type: MealType | None = Query(default=None),
) -> DiaryDayOut:
    """Repete os lançamentos de um dia anterior (opcionalmente só uma refeição)."""
    query = (
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user.id)
        .where(DiaryEntry.entry_date == from_day)
    )
    if meal_type is not None:
        query = query.where(DiaryEntry.meal_type == meal_type)
    for src in session.exec(query).all():
        session.add(
            DiaryEntry(
                user_id=user.id,
                entry_date=day,
                meal_type=src.meal_type,
                source=src.source,
                food_id=src.food_id,
                recipe_id=src.recipe_id,
                quantity=src.quantity,
                name_snapshot=src.name_snapshot,
                kcal=src.kcal,
                protein_g=src.protein_g,
                carbs_g=src.carbs_g,
                fat_g=src.fat_g,
            )
        )
    session.commit()
    return get_diary(user, session, day)
