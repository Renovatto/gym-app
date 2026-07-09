"""Motor de recomendacao da dieta (deterministico e explicavel).

Duas portas, o mesmo motor:
  - suggest_gap: dado o alvo do dia e o que ja foi comido, sugere alimentos que
    fecham a lacuna (proteina primeiro, o macro que mais importa pro objetivo).
  - substitutes: troca um alimento por equivalentes da mesma categoria, ajustando
    a porcao para igualar o macro-ancora da categoria e mostrando a diferenca de kcal.

Regra de ouro: escolhe/combina alimentos REAIS do catalogo; nunca inventa macro.
Todo alimento guarda valores por 100 g; a porcao e sempre em gramas.
"""

from collections import Counter
from datetime import date

from sqlmodel import desc, select
from sqlmodel import Session

from ..models import (
    DiaryEntry,
    EntrySource,
    Food,
    FoodCategory,
    MealType,
    Objective,
    Profile,
    User,
    WeightLog,
)
from ..schemas import (
    DiaryGapOut,
    FoodSuggestionOut,
    MacrosOut,
    MealPlanMealOut,
    MealPlanOut,
    SubstituteItemOut,
    SubstitutesOut,
    SubstituteSourceOut,
)
from .diet import food_macros, to_food_out
from .dietplan import maintenance_override as _maintenance_override
from .goals import compute_goals

# Macro-ancora de cada categoria: o macro que a troca equivalente mantem igual.
# Categorias mistas (bebida/outros) caem em calorias.
_CATEGORY_ANCHOR: dict[FoodCategory, str] = {
    FoodCategory.protein: "protein_g",
    FoodCategory.dairy: "protein_g",
    FoodCategory.legume: "protein_g",
    FoodCategory.carb: "carbs_g",
    FoodCategory.fruit: "carbs_g",
    FoodCategory.sweet: "carbs_g",
    FoodCategory.vegetable: "carbs_g",
    FoodCategory.fat: "fat_g",
    FoodCategory.beverage: "kcal",
    FoodCategory.other: "kcal",
}

# Nome do atributo (Food/MacrosOut) -> codigo enviado ao front (que faz o i18n).
_ANCHOR_CODE = {"protein_g": "protein", "carbs_g": "carbs", "fat_g": "fat", "kcal": "calories"}

# Limiares para considerar que "falta" um macro (evita sugerir por 2 g de sobra).
_MIN_PROTEIN_GAP = 5.0  # g
_MIN_MACRO_GAP = 5.0  # g (carbo/gordura)
_MIN_KCAL_GAP = 60.0  # kcal


def _attr(obj: object, name: str) -> float:
    """Le protein_g/carbs_g/fat_g/kcal de um Food ou de um MacrosOut (mesmos nomes)."""
    return float(getattr(obj, name))


def _sensible_portion(grams: float) -> float:
    """Porcao 'de gente': entre 15 g e 400 g, arredondada a cada 5 g."""
    grams = max(15.0, min(grams, 400.0))
    return round(grams / 5.0) * 5.0


def _visible_foods(
    session: Session, user_id: int, category: FoodCategory | None = None
) -> list[Food]:
    query = select(Food).where((Food.user_id.is_(None)) | (Food.user_id == user_id))
    if category is not None:
        query = query.where(Food.category == category)
    return list(session.exec(query).all())


def _food_frequency(session: Session, user_id: int) -> Counter:
    """Quantas vezes o usuario ja lancou cada alimento (para personalizar o ranking)."""
    rows = session.exec(
        select(DiaryEntry.food_id)
        .where(DiaryEntry.user_id == user_id)
        .where(DiaryEntry.source == EntrySource.food)
        .where(DiaryEntry.food_id.is_not(None))
    ).all()
    return Counter(fid for fid in rows if fid is not None)


def _daily_target(session: Session, user_id: int) -> MacrosOut | None:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    latest = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user_id)
        .order_by(desc(WeightLog.logged_at), desc(WeightLog.id))
    ).first()
    if profile is None or latest is None:
        return None
    g = compute_goals(
        profile, latest.weight_kg, maintenance_override=_maintenance_override(session, user_id)
    )
    return MacrosOut(kcal=g.target_kcal, protein_g=g.protein_g, carbs_g=g.carbs_g, fat_g=g.fat_g)


def _consumed(session: Session, user_id: int, day: date) -> MacrosOut:
    entries = session.exec(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user_id)
        .where(DiaryEntry.entry_date == day)
    ).all()
    return MacrosOut(
        kcal=round(sum(e.kcal for e in entries), 1),
        protein_g=round(sum(e.protein_g for e in entries), 1),
        carbs_g=round(sum(e.carbs_g for e in entries), 1),
        fat_g=round(sum(e.fat_g for e in entries), 1),
    )


def _remaining(goals: MacrosOut, consumed: MacrosOut) -> MacrosOut:
    """Falta = meta - consumido, nunca negativo."""
    return MacrosOut(
        kcal=round(max(goals.kcal - consumed.kcal, 0), 1),
        protein_g=round(max(goals.protein_g - consumed.protein_g, 0), 1),
        carbs_g=round(max(goals.carbs_g - consumed.carbs_g, 0), 1),
        fat_g=round(max(goals.fat_g - consumed.fat_g, 0), 1),
    )


def _choose_primary(remaining: MacrosOut) -> tuple[str, str] | None:
    """Macro-alvo: proteina primeiro (prioridade pro objetivo); senao o macro
    (carbo/gordura) com maior falta; senao calorias. None = nada relevante falta."""
    if remaining.protein_g >= _MIN_PROTEIN_GAP:
        return "protein_g", "protein"
    if remaining.carbs_g >= _MIN_MACRO_GAP or remaining.fat_g >= _MIN_MACRO_GAP:
        if remaining.carbs_g >= remaining.fat_g:
            return "carbs_g", "carbs"
        return "fat_g", "fat"
    if remaining.kcal >= _MIN_KCAL_GAP:
        return "kcal", "calories"
    return None


def _rank_suggestions(
    session: Session, user: User, remaining: MacrosOut, primary_attr: str,
    freq: Counter, max_freq: int, limit: int,
) -> list[FoodSuggestionOut]:
    """Ranqueia alimentos que fecham a lacuna informada (do dia ou de uma refeicao).

    Cada sugestao usa uma PORCAO NATURAL do alimento (a porcao padrao), nunca uma
    quantidade absurda pra fechar sozinha - o usuario vai somando itens. Ainda limita
    pela caloria que cabe (no fim do dia/refeicao, porcoes menores)."""
    need = _attr(remaining, primary_attr)
    candidates: list[tuple[Food, float, MacrosOut, float, float]] = []
    for food in _visible_foods(session, user.id):
        if _attr(food, primary_attr) <= 0:
            continue  # nao ajuda a fechar o macro-alvo
        portion = food.default_portion_g or 100.0
        if remaining.kcal > 0 and food.kcal > 0:
            portion = min(portion, remaining.kcal / (food.kcal / 100.0))
        portion = _sensible_portion(portion)
        macros = food_macros(food, portion)
        delivered = _attr(macros, primary_attr)
        if delivered <= 0:
            continue
        # densidade = macro-alvo por caloria (premia alimento "limpo", ex.: proteina magra)
        density = delivered / max(macros.kcal, 1.0)
        candidates.append((food, portion, macros, delivered, density))

    max_density = max((c[4] for c in candidates), default=1.0) or 1.0
    scored: list[tuple[float, Food, float, MacrosOut]] = []
    for food, portion, macros, delivered, density in candidates:
        # Nota = o quanto a porcao cobre da lacuna + densidade do macro + o quanto
        # voce ja usa aquele alimento (personalizacao).
        coverage = min(delivered / need, 1.0) if need > 0 else 0.0
        density_norm = density / max_density
        freq_bonus = (freq.get(food.id, 0) / max_freq) if max_freq else 0.0
        score = coverage + 0.8 * density_norm + 0.2 * freq_bonus
        scored.append((score, food, portion, macros))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        FoodSuggestionOut(food=to_food_out(food, user.locale), grams=grams, macros=macros)
        for _, food, grams, macros in scored[:limit]
    ]


def suggest_gap(session: Session, user: User, day: date, limit: int = 4) -> DiaryGapOut:
    """O que falta hoje + alimentos que fecham a lacuna (motor reativo)."""
    goals = _daily_target(session, user.id)
    consumed = _consumed(session, user.id, day)
    if goals is None:
        # perfil/pesagem incompletos: sem metas nao ha o que recomendar
        return DiaryGapOut(
            date=day, goals=None, consumed=consumed, remaining=None,
            primary="no_goal", suggestions=[],
        )

    remaining = _remaining(goals, consumed)
    chosen = _choose_primary(remaining)
    if chosen is None:
        return DiaryGapOut(
            date=day, goals=goals, consumed=consumed, remaining=remaining,
            primary="complete", suggestions=[],
        )
    primary_attr, primary_code = chosen
    freq = _food_frequency(session, user.id)
    max_freq = max(freq.values(), default=1)
    suggestions = _rank_suggestions(session, user, remaining, primary_attr, freq, max_freq, limit)
    return DiaryGapOut(
        date=day, goals=goals, consumed=consumed, remaining=remaining,
        primary=primary_code, suggestions=suggestions,
    )


# --- Fase 2: cardapio consultivo (plano por refeicao) ---------------------

# Estrutura de refeicoes recomendada por objetivo: a fatia de cada horario no alvo
# diario. Ganho: refeicoes mais parelhas (lanche maior); perda: front-load com lanche
# menor; manutencao/recomp: divisao classica.
_MEAL_SHARES: dict[Objective, dict[MealType, float]] = {
    Objective.lose_fat: {
        MealType.breakfast: 0.30,
        MealType.lunch: 0.35,
        MealType.snack: 0.10,
        MealType.dinner: 0.25,
    },
    Objective.gain_muscle: {
        MealType.breakfast: 0.25,
        MealType.lunch: 0.30,
        MealType.snack: 0.20,
        MealType.dinner: 0.25,
    },
}
_DEFAULT_SHARES: dict[MealType, float] = {
    MealType.breakfast: 0.25,
    MealType.lunch: 0.35,
    MealType.snack: 0.15,
    MealType.dinner: 0.25,
}


def _sum_entries(entries: list[DiaryEntry]) -> MacrosOut:
    return MacrosOut(
        kcal=round(sum(e.kcal for e in entries), 1),
        protein_g=round(sum(e.protein_g for e in entries), 1),
        carbs_g=round(sum(e.carbs_g for e in entries), 1),
        fat_g=round(sum(e.fat_g for e in entries), 1),
    )


def _scale(macros: MacrosOut, factor: float) -> MacrosOut:
    return MacrosOut(
        kcal=round(macros.kcal * factor, 1),
        protein_g=round(macros.protein_g * factor, 1),
        carbs_g=round(macros.carbs_g * factor, 1),
        fat_g=round(macros.fat_g * factor, 1),
    )


def _bounded_remaining(target: MacrosOut, consumed: MacrosOut, day_left: MacrosOut) -> MacrosOut:
    """Lacuna de uma refeicao: nao passa do alvo dela NEM do que ainda falta no dia
    (por isso, uma vez o dia batido, nenhuma refeicao sugere mais - adaptativo)."""
    def field(attr: str) -> float:
        return round(max(0.0, min(_attr(target, attr) - _attr(consumed, attr), _attr(day_left, attr))), 1)

    return MacrosOut(
        kcal=field("kcal"), protein_g=field("protein_g"),
        carbs_g=field("carbs_g"), fat_g=field("fat_g"),
    )


def meal_plan(session: Session, user: User, day: date, limit: int = 3) -> MealPlanOut:
    """Cardapio consultivo: por refeicao, o alvo, o que ja tem e sugestoes que fecham."""
    goals = _daily_target(session, user.id)
    if goals is None:
        return MealPlanOut(date=day, goals=None, meals=[])

    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    shares = _MEAL_SHARES.get(profile.objective, _DEFAULT_SHARES) if profile else _DEFAULT_SHARES

    entries = list(
        session.exec(
            select(DiaryEntry)
            .where(DiaryEntry.user_id == user.id)
            .where(DiaryEntry.entry_date == day)
        ).all()
    )
    remaining_day = _remaining(goals, _sum_entries(entries))
    freq = _food_frequency(session, user.id)
    max_freq = max(freq.values(), default=1)

    meals: list[MealPlanMealOut] = []
    for meal_type, share in shares.items():
        target = _scale(goals, share)
        consumed_meal = _sum_entries([e for e in entries if e.meal_type == meal_type])
        meal_remaining = _bounded_remaining(target, consumed_meal, remaining_day)
        chosen = _choose_primary(meal_remaining)
        suggestions = (
            _rank_suggestions(session, user, meal_remaining, chosen[0], freq, max_freq, limit)
            if chosen is not None
            else []
        )
        meals.append(
            MealPlanMealOut(
                meal_type=meal_type,
                target=target,
                consumed=consumed_meal,
                remaining=meal_remaining,
                primary=chosen[1] if chosen else "complete",
                suggestions=suggestions,
            )
        )
    return MealPlanOut(date=day, goals=goals, meals=meals)


def substitutes(
    session: Session, user: User, food: Food, grams: float, limit: int = 6
) -> SubstitutesOut:
    """Equivalentes na mesma categoria, igualando o macro-ancora e mostrando o delta de kcal."""
    anchor = _CATEGORY_ANCHOR.get(food.category, "kcal")
    source_macros = food_macros(food, grams)
    source_anchor_value = _attr(source_macros, anchor)  # anchor pode ser 'kcal'
    freq = _food_frequency(session, user.id)

    ranked: list[tuple[float, Food, float, MacrosOut, float]] = []
    for cand in _visible_foods(session, user.id, category=food.category):
        if cand.id == food.id:
            continue
        cand_per100 = _attr(cand, anchor)
        if cand_per100 <= 0:
            continue
        # Escala a porcao pra igualar o macro-ancora do original.
        if source_anchor_value > 0:
            cand_grams = _sensible_portion(source_anchor_value / (cand_per100 / 100.0))
        else:
            cand_grams = _sensible_portion(cand.default_portion_g)
        cand_macros = food_macros(cand, cand_grams)
        kcal_delta = round(cand_macros.kcal - source_macros.kcal, 1)
        # Distancia = o quanto os OUTROS macros se afastam do original (o ancora ja
        # bate). Alimentos seus/frequentes recebem um empurrao no ranking.
        distance = (
            abs(cand_macros.protein_g - source_macros.protein_g)
            + abs(cand_macros.carbs_g - source_macros.carbs_g)
            + abs(cand_macros.fat_g - source_macros.fat_g)
            + 0.05 * abs(kcal_delta)
        )
        if cand.user_id is not None or freq.get(cand.id):
            distance *= 0.85
        ranked.append((distance, cand, cand_grams, cand_macros, kcal_delta))

    ranked.sort(key=lambda item: item[0])
    items = [
        SubstituteItemOut(
            food=to_food_out(cand, user.locale), grams=grams_, macros=macros, kcal_delta=delta
        )
        for _, cand, grams_, macros, delta in ranked[:limit]
    ]
    return SubstitutesOut(
        source=SubstituteSourceOut(
            food=to_food_out(food, user.locale), grams=grams, macros=source_macros
        ),
        anchor=_ANCHOR_CODE.get(anchor, "calories"),
        items=items,
    )
