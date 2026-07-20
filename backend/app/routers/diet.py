from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, desc, select

from ..deps import CurrentUser, SessionDep
from ..models import (
    DiaryEntry,
    EntrySource,
    FavoriteKind,
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
    DiaryEntryUpdate,
    DiaryFromLibraryIn,
    DietAdherenceOut,
    DietPeriodOut,
    DiaryGapOut,
    ExternalFoodOut,
    FavoriteToggleIn,
    FavoriteToggleOut,
    FoodIn,
    FoodOut,
    MacrosOut,
    MealGroupOut,
    MealPlanOut,
    LibraryRecipeOut,
    RecipeIn,
    RecipeOut,
    SubstitutesOut,
)
from ..services.coaching import diet_adherence
from ..services.dietplan import maintenance_override as diet_maintenance_override
from ..services.dietplan import period_out as diet_period_out
from ..services.dietplan import renew as renew_diet_period
from ..services.foodsearch import search_external
from ..services.diet import (
    food_macros,
    localized_food_name,
    recipe_breakdown,
    sum_macros,
    to_food_out,
)
from ..services.favorites import favorite_food_ids, favorite_recipe_ids, toggle_favorite
from ..services.goals import compute_goals
from ..services.recipes_library import adopt as adopt_library_recipe
from ..services.recipes_library import get_one as get_library_recipe
from ..services.recipes_library import list_library
from ..services.recommend import meal_plan as compute_meal_plan
from ..services.recommend import substitutes as compute_substitutes
from ..services.recommend import suggest_gap
from ..services.text import normalize_search

router = APIRouter(tags=["diet"])


# --- Alimentos ------------------------------------------------------------


@router.get("/foods", response_model=list[FoodOut])
def list_foods(
    user: CurrentUser,
    session: SessionDep,
    q: str = Query(default="", max_length=60),
    category: FoodCategory | None = Query(default=None),
    # scope=mine filtra so os alimentos criados pelo proprio usuario (a etiqueta "meu"),
    # que sem isso podiam ficar fora do corte de "limit" quando o catalogo global e grande.
    scope: str | None = Query(default=None, pattern=r"^(mine)$"),
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[FoodOut]:
    query = select(Food).where((Food.user_id.is_(None)) | (Food.user_id == user.id))
    if scope == "mine":
        query = query.where(Food.user_id == user.id)
    if category is not None:
        query = query.where(Food.category == category)
    foods = session.exec(query).all()

    term = normalize_search(q.strip())
    fav_ids = favorite_food_ids(session, user.id)
    out = []
    for food in foods:
        name = localized_food_name(food, user.locale)
        if term and term not in normalize_search(name):
            # também busca em qualquer idioma cadastrado (ex.: nome em inglês)
            if not any(term in normalize_search(t.name) for t in food.translations):
                continue
        out.append(to_food_out(food, user.locale, fav_ids))
    # favoritos primeiro, depois alfabetica
    out.sort(key=lambda f: (not f.is_favorite, f.name.lower()))
    return out[offset : offset + limit]


@router.get("/me/foods/favorites", response_model=list[FoodOut])
def favorite_foods(user: CurrentUser, session: SessionDep) -> list[FoodOut]:
    """Alimentos que o usuario marcou como favoritos (a estrelinha)."""
    fav_ids = favorite_food_ids(session, user.id)
    out = [
        to_food_out(food, user.locale, fav_ids)
        for food_id in fav_ids
        if (food := _visible_food(session, food_id, user.id)) is not None
    ]
    out.sort(key=lambda f: f.name.lower())
    return out


@router.get("/me/foods/recent", response_model=list[FoodOut])
def recent_foods(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=12, ge=1, le=40),
) -> list[FoodOut]:
    """Alimentos lançados mais recentemente pelo usuário, sem repetir."""
    rows = session.exec(
        select(DiaryEntry.food_id)
        .where(DiaryEntry.user_id == user.id)
        .where(DiaryEntry.source == EntrySource.food)
        .where(DiaryEntry.food_id.is_not(None))
        .order_by(desc(DiaryEntry.logged_at))
    ).all()
    seen: list[int] = []
    for food_id in rows:
        if food_id not in seen:
            seen.append(food_id)
        if len(seen) >= limit:
            break
    fav_ids = favorite_food_ids(session, user.id)
    out = []
    for food_id in seen:
        food = _visible_food(session, food_id, user.id)
        if food is not None:
            out.append(to_food_out(food, user.locale, fav_ids))
    return out


@router.put("/me/favorites", response_model=FavoriteToggleOut)
def toggle_favorite_endpoint(
    data: FavoriteToggleIn, user: CurrentUser, session: SessionDep
) -> FavoriteToggleOut:
    """Liga/desliga a estrelinha de um alimento ou receita. Valida que o item existe
    e pertence ao usuario (ou e global, no caso de alimento do catalogo)."""
    if data.kind == FavoriteKind.food:
        if _visible_food(session, data.ref_id, user.id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="FOOD_NOT_FOUND")
    else:
        if _get_owned_recipe_or_none(session, data.ref_id, user.id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="RECIPE_NOT_FOUND")
    now_favorite = toggle_favorite(session, user.id, data.kind, data.ref_id)
    return FavoriteToggleOut(favorite=now_favorite)


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


@router.put("/me/foods/{food_id}", response_model=FoodOut)
def update_food(food_id: int, data: FoodIn, user: CurrentUser, session: SessionDep) -> FoodOut:
    """So o dono pode editar (nunca um alimento global do catalogo)."""
    food = session.get(Food, food_id)
    if food is None or food.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="FOOD_NOT_FOUND")
    food.category = data.category
    food.kcal = data.kcal
    food.protein_g = data.protein_g
    food.carbs_g = data.carbs_g
    food.fat_g = data.fat_g
    food.default_portion_g = data.default_portion_g
    session.add(food)
    translation = session.exec(
        select(FoodTranslation)
        .where(FoodTranslation.food_id == food.id)
        .where(FoodTranslation.locale == user.locale)
    ).first()
    if translation is not None:
        translation.name = data.name.strip()
        session.add(translation)
    else:
        session.add(FoodTranslation(food_id=food.id, locale=user.locale, name=data.name.strip()))
    session.commit()
    session.refresh(food)
    fav_ids = favorite_food_ids(session, user.id)
    return to_food_out(food, user.locale, fav_ids)


@router.delete("/me/foods/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food(food_id: int, user: CurrentUser, session: SessionDep) -> None:
    food = session.get(Food, food_id)
    if food is None or food.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="FOOD_NOT_FOUND")
    # nao deixa excluir se estiver em uso (receita ou historico do diario) - evita
    # violar a FK no Postgres com um erro cru; a mensagem aqui e clara e traduzivel.
    in_recipe = session.exec(
        select(RecipeIngredient).where(RecipeIngredient.food_id == food_id)
    ).first()
    if in_recipe is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="FOOD_IN_USE_RECIPE")
    in_diary = session.exec(select(DiaryEntry).where(DiaryEntry.food_id == food_id)).first()
    if in_diary is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="FOOD_IN_USE_DIARY")
    session.delete(food)
    session.commit()


@router.get("/me/foods/{food_id}/substitutes", response_model=SubstitutesOut)
def food_substitutes(
    food_id: int,
    user: CurrentUser,
    session: SessionDep,
    grams: float = Query(..., gt=0, le=2000, description="Porcao atual em gramas"),
    limit: int = Query(default=6, ge=1, le=12),
) -> SubstitutesOut:
    """Equivalentes na mesma categoria, igualando o macro-ancora (troca inteligente)."""
    food = _visible_food(session, food_id, user.id)
    if food is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="FOOD_NOT_FOUND")
    return compute_substitutes(session, user, food, grams, limit)


@router.get("/me/foods/search-external", response_model=list[ExternalFoodOut])
def search_external_foods(
    user: CurrentUser,
    q: str = Query(..., min_length=2, max_length=80, description="Nome do produto"),
    limit: int = Query(default=15, ge=1, le=30),
) -> list[ExternalFoodOut]:
    """Busca alimentos na base aberta (Open Food Facts) para importar ao catalogo."""
    # locale do usuario -> codigo de idioma do OFF (pt-BR -> pt, en -> en, es -> es)
    lang = user.locale.split("-")[0].lower()
    return search_external(q, limit, lang)


# --- Receitas -------------------------------------------------------------


def _visible_food(session: Session, food_id: int, user_id: int) -> Food | None:
    food = session.get(Food, food_id)
    if food is None or (food.user_id is not None and food.user_id != user_id):
        return None
    return food


def _recipe_out(
    session: Session, recipe: Recipe, locale: str, is_favorite: bool = False
) -> RecipeOut:
    ings, total, per_serving = recipe_breakdown(session, recipe, locale)
    return RecipeOut(
        id=recipe.id,
        name=recipe.name,
        servings=recipe.servings,
        ingredients=ings,
        total=total,
        per_serving=per_serving,
        is_favorite=is_favorite,
    )


def _get_owned_recipe_or_none(session: Session, recipe_id: int, user_id: int) -> Recipe | None:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None or recipe.user_id != user_id:
        return None
    return recipe


@router.get("/me/recipes", response_model=list[RecipeOut])
def list_recipes(user: CurrentUser, session: SessionDep) -> list[RecipeOut]:
    recipes = session.exec(
        select(Recipe).where(Recipe.user_id == user.id).order_by(desc(Recipe.created_at))
    ).all()
    fav_ids = favorite_recipe_ids(session, user.id)
    out = [_recipe_out(session, r, user.locale, r.id in fav_ids) for r in recipes]
    # favoritas primeiro, mantendo a ordem por criacao dentro de cada grupo
    out.sort(key=lambda r: not r.is_favorite)
    return out


@router.get("/recipes/library", response_model=list[LibraryRecipeOut])
def recipes_library(
    user: CurrentUser,
    session: SessionDep,
    tag: str | None = Query(default=None, max_length=20),
) -> list[LibraryRecipeOut]:
    """Biblioteca de receitas semente: macros calculados dos ingredientes do catalogo."""
    return list_library(session, user, tag)


@router.get("/recipes/library/{slug}", response_model=LibraryRecipeOut)
def library_recipe_detail(slug: str, user: CurrentUser, session: SessionDep) -> LibraryRecipeOut:
    """Detalhe de uma receita da biblioteca (ingredientes + macros) para visualizar."""
    recipe = get_library_recipe(session, user, slug)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="RECIPE_NOT_FOUND")
    return recipe


@router.post("/me/recipes/from-library/{slug}", response_model=RecipeOut)
def adopt_recipe(slug: str, user: CurrentUser, session: SessionDep) -> RecipeOut:
    """Copia uma receita da biblioteca para as receitas do usuario (editavel)."""
    recipe = adopt_library_recipe(session, user, slug)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="RECIPE_NOT_FOUND")
    return _recipe_out(session, recipe, user.locale)


@router.post(
    "/me/diary/from-library", response_model=DiaryEntryOut, status_code=status.HTTP_201_CREATED
)
def add_from_library(
    data: DiaryFromLibraryIn, user: CurrentUser, session: SessionDep
) -> DiaryEntryOut:
    """1 toque: adota a receita da biblioteca (idempotente) e lanca a porcao no diario."""
    recipe = adopt_library_recipe(session, user, data.slug)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="RECIPE_NOT_FOUND")
    macros, name = _entry_macros_and_name(
        session, user.id, user.locale, EntrySource.recipe, None, recipe.id, data.quantity
    )
    entry = DiaryEntry(
        user_id=user.id,
        entry_date=data.entry_date,
        meal_type=data.meal_type,
        source=EntrySource.recipe,
        recipe_id=recipe.id,
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
    g = compute_goals(
        profile, latest.weight_kg, maintenance_override=diet_maintenance_override(session, user_id)
    )
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


@router.get("/me/diary/logged-days", response_model=list[date])
def diary_logged_days(
    user: CurrentUser,
    session: SessionDep,
    start: date = Query(..., description="Inicio do intervalo (inclusive)"),
    end: date = Query(..., description="Fim do intervalo (inclusive)"),
) -> list[date]:
    """Dias com pelo menos um lancamento no intervalo (para marcar no calendario)."""
    rows = session.exec(
        select(DiaryEntry.entry_date)
        .where(DiaryEntry.user_id == user.id)
        .where(DiaryEntry.entry_date >= start)
        .where(DiaryEntry.entry_date <= end)
    ).all()
    return sorted(set(rows))


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


@router.get("/me/diary/gap", response_model=DiaryGapOut)
def diary_gap(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (YYYY-MM-DD)"),
    limit: int = Query(default=4, ge=1, le=8),
) -> DiaryGapOut:
    """O que falta pra fechar as metas do dia + alimentos que encaixam na lacuna."""
    return suggest_gap(session, user, day, limit)


@router.get("/me/diary/meal-plan", response_model=MealPlanOut)
def diary_meal_plan(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (YYYY-MM-DD)"),
    limit: int = Query(default=3, ge=1, le=6),
) -> MealPlanOut:
    """Cardapio consultivo: por refeicao, o alvo recomendado + sugestoes que fecham."""
    return compute_meal_plan(session, user, day, limit)


@router.get("/me/diet/adherence", response_model=DietAdherenceOut)
def diet_adherence_endpoint(
    user: CurrentUser,
    session: SessionDep,
    end: date = Query(..., description="Ultimo dia da janela (dia local do cliente)"),
    window: int = Query(default=7, ge=1, le=30),
) -> DietAdherenceOut:
    """Aderencia (recomendado x real) das ultimas janelas de dias."""
    return diet_adherence(session, user, end, window)


@router.get("/me/diet/period", response_model=DietPeriodOut | None)
def diet_period(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (YYYY-MM-DD)"),
) -> DietPeriodOut | None:
    """Periodo (vigencia) da meta de dieta: inicio, validade e objetivo."""
    return diet_period_out(session, user, day)


@router.post("/me/diet/period/renew", response_model=DietPeriodOut | None)
def diet_period_renew(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(...),
    adopt_maintenance_kcal: int | None = Query(default=None, ge=800, le=6000),
) -> DietPeriodOut | None:
    """Renova o periodo. Se adopt_maintenance_kcal vier, a meta passa a sair da
    manutencao real medida (override); senao segue a formula do perfil."""
    return renew_diet_period(session, user, day, adopt_maintenance_kcal)


def _entry_macros_and_name(
    session: Session, user_id: int, locale: str, source: EntrySource,
    food_id: int | None, recipe_id: int | None, quantity: float
) -> tuple[MacrosOut, str]:
    if source == EntrySource.food:
        if food_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="FOOD_REQUIRED")
        food = _visible_food(session, food_id, user_id)
        if food is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="FOOD_NOT_FOUND")
        return food_macros(food, quantity), localized_food_name(food, locale)
    if recipe_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="RECIPE_REQUIRED")
    recipe = _get_owned_recipe(session, recipe_id, user_id)
    _, _, per_serving = recipe_breakdown(session, recipe, locale)
    macros = MacrosOut(
        kcal=round(per_serving.kcal * quantity, 1),
        protein_g=round(per_serving.protein_g * quantity, 1),
        carbs_g=round(per_serving.carbs_g * quantity, 1),
        fat_g=round(per_serving.fat_g * quantity, 1),
    )
    return macros, recipe.name


@router.post("/me/diary", response_model=DiaryEntryOut, status_code=status.HTTP_201_CREATED)
def add_diary_entry(data: DiaryEntryIn, user: CurrentUser, session: SessionDep) -> DiaryEntryOut:
    macros, name = _entry_macros_and_name(
        session, user.id, user.locale, data.source, data.food_id, data.recipe_id, data.quantity
    )
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


@router.put("/me/diary/{entry_id}", response_model=DiaryEntryOut)
def update_diary_entry(
    entry_id: int, data: DiaryEntryUpdate, user: CurrentUser, session: SessionDep
) -> DiaryEntryOut:
    entry = session.get(DiaryEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ENTRY_NOT_FOUND")
    macros, name = _entry_macros_and_name(
        session, user.id, user.locale, entry.source, entry.food_id, entry.recipe_id, data.quantity
    )
    entry.quantity = data.quantity
    entry.name_snapshot = name
    entry.kcal = macros.kcal
    entry.protein_g = macros.protein_g
    entry.carbs_g = macros.carbs_g
    entry.fat_g = macros.fat_g
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
