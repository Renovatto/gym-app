"""Motor de recomendacao da dieta (deterministico e explicavel).

Tres portas, o mesmo motor:
  - suggest_gap: dado o alvo do dia e o que ja foi comido, sugere alimentos que
    fecham a lacuna (proteina primeiro, o macro que mais importa pro objetivo).
  - substitutes: troca um alimento por equivalentes da mesma categoria, ajustando
    a porcao para igualar o macro-ancora da categoria e mostrando a diferenca de kcal.
  - build_meal: dado o que a pessoa diz que tem em casa (+ itens basicos), monta
    receitas/alimentos que fecham a lacuna com o que e de fato possivel cozinhar agora.

Regra de ouro: escolhe/combina alimentos REAIS do catalogo; nunca inventa macro.
Todo alimento guarda valores por 100 g; a porcao e sempre em gramas.
"""

from collections import Counter
from datetime import date, timedelta

from sqlmodel import desc, select
from sqlmodel import Session

from .cycle import PHASE_BONUS, PHASE_MIN_COVERAGE, phase_boost_food_ids
from ..models import (
    DiaryEntry,
    EntrySource,
    Food,
    FoodCategory,
    MealType,
    Objective,
    Profile,
    Recipe,
    User,
    WeightLog,
)
from ..schemas import (
    BuildMealOut,
    DiaryGapOut,
    FoodSuggestionOut,
    MacrosOut,
    MealPlanMealOut,
    MealPlanOut,
    PantryRecipeMatchOut,
    RecipeSuggestionOut,
    SubstituteItemOut,
    SubstitutesOut,
    SubstituteSourceOut,
)
from .diet import food_macros, to_food_out
from .dietplan import maintenance_override as _maintenance_override
from .favorites import favorite_food_ids, favorite_recipe_ids
from .goals import compute_goals
from .recipes_library import library_ingredient_food_ids_map, list_library

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
    FoodCategory.prepared: "kcal",
    FoodCategory.beverage: "kcal",
    FoodCategory.other: "kcal",
}

# Nome do atributo (Food/MacrosOut) -> codigo enviado ao front (que faz o i18n).
_ANCHOR_CODE = {"protein_g": "protein", "carbs_g": "carbs", "fat_g": "fat", "kcal": "calories"}

# Limiares para considerar que "falta" um macro (evita sugerir por 2 g de sobra).
_MIN_PROTEIN_GAP = 5.0  # g
_MIN_MACRO_GAP = 5.0  # g (carbo/gordura)
_MIN_KCAL_GAP = 60.0  # kcal

# Janela de "recente" pro ranking de frequencia: reflete o habito ATUAL (o que a
# pessoa realmente tem comido), nao a dieta de meses/anos atras - um alimento comido
# 20x ha 1 ano nao deveria pesar mais que um comido 3x essa semana.
_RECENT_DAYS = 60

# "Montar refeicao com o que tenho em casa": itens basicos que quase toda cozinha tem,
# contam como "tem" automaticamente (senao quase nenhuma receita bateria 100%).
_STAPLE_SLUGS: set[str] = {
    "olive-oil", "sunflower-oil", "coconut-oil", "butter",
    "garlic", "onion", "salt", "sugar",
}
# Abaixo deste tanto de ingredientes NAO-basicos presentes, a receita nem aparece -
# realismo importa mais que "e mais gostosa" aqui (a reclamacao era sugestao irreal).
_MIN_PANTRY_MATCH_RATIO = 0.34


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


def _staple_food_ids(session: Session) -> set[int]:
    """Ids globais dos itens basicos (ver _STAPLE_SLUGS) - sempre contam como 'tem'."""
    rows = session.exec(
        select(Food.id).where(Food.user_id.is_(None)).where(Food.slug.in_(_STAPLE_SLUGS))
    ).all()
    return set(rows)


def _food_frequency(session: Session, user_id: int, today: date) -> Counter:
    """Quantas vezes o usuario lancou cada alimento nos ultimos _RECENT_DAYS dias
    (para personalizar o ranking pelo habito atual, ver _RECENT_DAYS)."""
    since = today - timedelta(days=_RECENT_DAYS)
    rows = session.exec(
        select(DiaryEntry.food_id)
        .where(DiaryEntry.user_id == user_id)
        .where(DiaryEntry.source == EntrySource.food)
        .where(DiaryEntry.food_id.is_not(None))
        .where(DiaryEntry.entry_date >= since)
    ).all()
    return Counter(fid for fid in rows if fid is not None)


def _meal_food_frequency(session: Session, user_id: int, meal_type: MealType, today: date) -> Counter:
    """Como _food_frequency, mas so conta lancamentos NAQUELE tipo de refeicao - o
    sinal que realmente evita sugestao fora de hora (ex.: camarao no cafe da manha):
    um alimento so pesa aqui se a pessoa MESMA ja comeu ele nesse horario antes."""
    since = today - timedelta(days=_RECENT_DAYS)
    rows = session.exec(
        select(DiaryEntry.food_id)
        .where(DiaryEntry.user_id == user_id)
        .where(DiaryEntry.source == EntrySource.food)
        .where(DiaryEntry.food_id.is_not(None))
        .where(DiaryEntry.meal_type == meal_type)
        .where(DiaryEntry.entry_date >= since)
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
    freq: Counter, max_freq: int, limit: int, favorite_ids: set[int],
    restrict_ids: set[int] | None = None,
    meal_freq: Counter | None = None, max_meal_freq: int = 0,
    phase_food_ids: set[int] | None = None, exclude_ids: set[int] | None = None,
) -> list[FoodSuggestionOut]:
    """Ranqueia alimentos que fecham a lacuna informada (do dia ou de uma refeicao).

    Cada sugestao usa uma PORCAO NATURAL do alimento (a porcao padrao), nunca uma
    quantidade absurda pra fechar sozinha - o usuario vai somando itens. Ainda limita
    pela caloria que cabe (no fim do dia/refeicao, porcoes menores).

    restrict_ids: quando informado, so considera esses alimentos (usado por
    'montar refeicao com o que tenho' pra restringir ao que a pessoa selecionou);
    None mantem o comportamento de sempre (todo o catalogo visivel).

    meal_freq/max_meal_freq: quantas vezes a PROPRIA pessoa ja comeu cada alimento
    NAQUELE tipo de refeicao (ver _meal_food_frequency) - pesa mais que a frequencia
    geral (freq) porque e o sinal mais direto de "isso faz sentido nesse horario pra
    mim", sem inventar regra generica de categoria (evita sugestao fora de hora, ex.
    camarao no cafe da manha, sem bloquear quem realmente come assim)."""
    need = _attr(remaining, primary_attr)
    candidates: list[tuple[Food, float, MacrosOut, float, float]] = []
    for food in _visible_foods(session, user.id):
        if restrict_ids is not None and food.id not in restrict_ids:
            continue
        if exclude_ids and food.id in exclude_ids:
            continue  # ja sugerido em outra refeicao do mesmo cardapio
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

    # UM alimento da fase recebe o bonus, nunca a lista toda. Sem este teto o cafe da
    # manha da fase menstrual saia com tres carnes seguidas e o da lutea com tres
    # peixes - a fase deixava de ajudar e passava a mandar. O escolhido e o que ja iria
    # melhor por merito proprio; os outros da fase continuam na disputa normal, sem
    # bonus, entao quem merece vaga sozinho nao perde nada.
    boosted_id: int | None = None
    if phase_food_ids:
        elegiveis = [
            (min(_attr(m, primary_attr) / need, 1.0) if need > 0 else 0.0, f.id)
            for f, _p, m, _d, _dens in candidates
            if f.id in phase_food_ids
        ]
        elegiveis = [(c, fid) for c, fid in elegiveis if c >= PHASE_MIN_COVERAGE]
        if elegiveis:
            boosted_id = max(elegiveis)[1]

    scored: list[tuple[float, Food, float, MacrosOut, bool]] = []
    for food, portion, macros, delivered, density in candidates:
        # Nota = o quanto a porcao cobre da lacuna + densidade do macro + o quanto
        # voce ja usa aquele alimento (personalizacao).
        coverage = min(delivered / need, 1.0) if need > 0 else 0.0
        density_norm = density / max_density
        freq_bonus = (freq.get(food.id, 0) / max_freq) if max_freq else 0.0
        meal_freq_bonus = (meal_freq.get(food.id, 0) / max_meal_freq) if meal_freq and max_meal_freq else 0.0
        # favorito e o sinal mais forte (voce DISSE que gosta); pesa acima da frequencia
        fav_bonus = 0.5 if food.id in favorite_ids else 0.0
        # Ciclo menstrual (opt-in): forte o bastante para o alimento da fase aparecer
        # onde a pessoa olha, mas so para UM item e so quando ele responde a lacuna do
        # dia (ver boosted_id acima e PHASE_MIN_COVERAGE).
        phase_bonus = PHASE_BONUS if food.id == boosted_id else 0.0
        score = coverage + 0.8 * density_norm + 0.2 * freq_bonus + 1.5 * meal_freq_bonus + fav_bonus + phase_bonus
        # so marca quem REALMENTE ganhou o bonus: dizer "da fase" num item que entrou
        # por merito proprio seria dar credito errado a fase
        scored.append((score, food, portion, macros, phase_bonus > 0))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        FoodSuggestionOut(
            food=to_food_out(food, user.locale, favorite_ids), grams=grams, macros=macros,
            from_phase=from_phase,
        )
        for _, food, grams, macros, from_phase in scored[:limit]
    ]


# Receita so entra como sugestao quando ainda falta bastante do dia/refeicao: lacuna
# pequena e coisa de alimento (um item), nao de um prato inteiro.
_MIN_RECIPE_KCAL_GAP = 250.0

# Afinidade suave entre refeicao e tags de receita (bonus no ranking, nao filtro duro):
# cafe/lanche puxam rapidas/doces; almoco/jantar puxam salgadas; pre-treino rapida+proteica.
_MEAL_TAG_AFFINITY: dict[MealType, set[str]] = {
    MealType.breakfast: {"quick", "sweet"},
    MealType.snack: {"quick", "sweet"},
    MealType.pre_workout: {"quick", "protein"},
    MealType.post_workout: {"protein", "quick"},
    MealType.supper: {"quick"},
    MealType.lunch: {"protein", "budget", "veggie"},
    MealType.dinner: {"protein", "budget", "veggie"},
}


def suggest_recipes(
    session: Session, user: User, remaining: MacrosOut,
    meal_type: MealType | None, limit: int = 2,
) -> list[RecipeSuggestionOut]:
    """Receitas da biblioteca que fecham a lacuna. Nota = cobertura do macro-alvo por
    UMA porcao + encaixe calorico (penaliza estourar) + afinidade refeicao<->tag +
    bonus se voce ja adotou/favoritou (a 'sua comida' aparece primeiro)."""
    if remaining.kcal < _MIN_RECIPE_KCAL_GAP:
        return []
    chosen = _choose_primary(remaining)
    primary_attr = chosen[0] if chosen else "kcal"
    need = _attr(remaining, primary_attr)

    library = list_library(session, user)  # ja traz per_serving, tags e is_favorite
    adopted_names = {
        r.name for r in session.exec(select(Recipe).where(Recipe.user_id == user.id)).all()
    }
    affinity = _MEAL_TAG_AFFINITY.get(meal_type, set()) if meal_type else set()

    scored: list[tuple[float, object]] = []
    for rec in library:
        per = rec.per_serving
        delivered = _attr(per, primary_attr)
        if delivered <= 0:
            continue
        coverage = min(delivered / need, 1.0) if need > 0 else 0.0
        # encaixe calorico: 1 se a porcao cabe no que falta; decai conforme estoura
        if per.kcal <= remaining.kcal:
            cal_fit = 1.0
        else:
            cal_fit = max(0.0, 1.0 - (per.kcal - remaining.kcal) / remaining.kcal)
        affinity_bonus = 0.3 if affinity.intersection(rec.tags) else 0.0
        # favorito > adotado > novidade (personalizacao)
        adopt_bonus = 0.5 if rec.is_favorite else (0.25 if rec.name in adopted_names else 0.0)
        score = coverage + 0.5 * cal_fit + affinity_bonus + adopt_bonus
        scored.append((score, rec))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        RecipeSuggestionOut(
            slug=rec.slug, name=rec.name, tags=rec.tags,
            macros=rec.per_serving, is_favorite=rec.is_favorite,
        )
        for _, rec in scored[:limit]
    ]


def suggest_gap(
    session: Session, user: User, day: date, limit: int = 4, meal_type: MealType | None = None,
) -> DiaryGapOut:
    """O que falta hoje + alimentos que fecham a lacuna (motor reativo).

    meal_type: refeicao "do horario agora" (o cliente ja calcula isso pra saber onde
    o botao de adicionar lanca por padrao) - quando informado, empurra o ranking pro
    que a pessoa costuma comer NAQUELE horario (ver _meal_food_frequency), deixando a
    sugestao mais realista sem travar quem quer ver o dia inteiro (None = comportamento
    de sempre, sem vies de horario)."""
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
    freq = _food_frequency(session, user.id, day)
    max_freq = max(freq.values(), default=1)
    fav_ids = favorite_food_ids(session, user.id)
    meal_freq, max_meal_freq = None, 0
    if meal_type is not None:
        meal_freq = _meal_food_frequency(session, user.id, meal_type, day)
        max_meal_freq = max(meal_freq.values(), default=0)
    suggestions = _rank_suggestions(
        session, user, remaining, primary_attr, freq, max_freq, limit, fav_ids,
        meal_freq=meal_freq, max_meal_freq=max_meal_freq,
        phase_food_ids=phase_boost_food_ids(session, user.id, day),
    )
    # receita usa a afinidade de tag existente quando ha horario; sem horario, sem afinidade
    recipe_suggestions = suggest_recipes(session, user, remaining, meal_type=meal_type)
    return DiaryGapOut(
        date=day, goals=goals, consumed=consumed, remaining=remaining,
        primary=primary_code, suggestions=suggestions, recipe_suggestions=recipe_suggestions,
    )


def phase_food_suggestions(
    session: Session, user: User, day: date, limit: int = 3
) -> list[FoodSuggestionOut]:
    """Alimentos da fase do ciclo que cabem no que falta do dia.

    Existe porque o bonus de desempate (PHASE_BONUS) e invisivel onde a pessoa olha:
    o ranking geral e dominado pela cobertura do macro que falta, entao um alimento
    da fase sobe algumas dezenas de posicoes sem nunca chegar aos 4 primeiros. Em vez
    de inflar o bonus - o que faria a fase atropelar o objetivo, exatamente o que o
    escopo proibe - a fase ganha lista propria, pequena e honesta: "isto aqui e da
    sua fase", ao lado da recomendacao normal, sem disputar com ela.

    Reusa o mesmo funil de sempre, so restringindo os candidatos (mesmo mecanismo do
    'montar refeicao com o que tenho'), entao a ordem continua respeitando o que
    falta no dia e a porcao continua sendo uma porcao de gente."""
    phase_ids = phase_boost_food_ids(session, user.id, day)
    if not phase_ids:
        return []
    goals = _daily_target(session, user.id)
    if goals is None:
        return []
    remaining = _remaining(goals, _consumed(session, user.id, day))
    chosen = _choose_primary(remaining)
    if chosen is None:
        return []  # dia fechado: nao ha lacuna para preencher
    freq = _food_frequency(session, user.id, day)
    return _rank_suggestions(
        session, user, remaining, chosen[0], freq, max(freq.values(), default=1),
        limit, favorite_food_ids(session, user.id), restrict_ids=phase_ids,
    )


def match_pantry_recipes(
    session: Session, user: User, remaining: MacrosOut, have_ids: set[int],
    meal_type: MealType | None, limit: int = 6,
) -> list[PantryRecipeMatchOut]:
    """Receitas da biblioteca que da pra cozinhar com o que a pessoa tem (+ basicos).

    match_ratio = fracao dos ingredientes NAO-basicos presentes em have_ids; receitas
    abaixo de _MIN_PANTRY_MATCH_RATIO nem entram (corte duro, nao so desconto de nota -
    "da pra fazer" importa mais que "e mais gostosa" nesta porta do motor). Dentro do
    corte, o peso do match_ratio no score (2.0) e maior que a soma de todos os outros
    bonus possiveis (~1.6), entao nenhuma combinacao de afinidade/favorito derruba uma
    receita 100%-compativel abaixo de uma parcial."""
    staple_ids = _staple_food_ids(session)
    ingredient_ids_by_slug = library_ingredient_food_ids_map(session)
    library = list_library(session, user)
    chosen = _choose_primary(remaining)
    primary_attr = chosen[0] if chosen else "kcal"
    need = _attr(remaining, primary_attr)
    affinity = _MEAL_TAG_AFFINITY.get(meal_type, set()) if meal_type else set()

    scored: list[tuple[float, object, float, MacrosOut, float, list[str]]] = []
    for rec in library:
        food_ids = ingredient_ids_by_slug.get(rec.slug)
        if food_ids is None:
            continue  # ingrediente sumiu do catalogo (mesmo criterio de list_library)

        non_staple = [
            (idx, fid) for idx, fid in enumerate(food_ids) if fid not in staple_ids
        ]
        if not non_staple:
            match_ratio, missing_idx = 1.0, []  # receita so tem basico (raro, ex.: molho)
        else:
            missing_idx = [idx for idx, fid in non_staple if fid not in have_ids]
            match_ratio = 1 - len(missing_idx) / len(non_staple)
        if match_ratio < _MIN_PANTRY_MATCH_RATIO:
            continue
        missing_names = [rec.ingredients[idx].name for idx in missing_idx]

        per = rec.per_serving
        delivered = _attr(per, primary_attr)
        # Escala a PORCAO (nao so pontua): entre 0.5x e 3x, arredondado a cada 0.5,
        # limitada tanto pelo macro-alvo quanto pela caloria que ainda cabe no dia.
        by_need = (need / delivered) if (need > 0 and delivered > 0) else 1.0
        by_kcal = (remaining.kcal / per.kcal) if per.kcal > 0 else 1.0
        quantity = round(max(0.5, min(by_need, by_kcal, 3.0)) * 2) / 2
        macros = _scale(per, quantity)

        coverage = min(_attr(macros, primary_attr) / need, 1.0) if need > 0 else 0.0
        if macros.kcal <= remaining.kcal:
            cal_fit = 1.0
        else:
            cal_fit = max(0.0, 1.0 - (macros.kcal - remaining.kcal) / remaining.kcal)
        affinity_bonus = 0.3 if affinity.intersection(rec.tags) else 0.0
        fav_bonus = 0.5 if rec.is_favorite else 0.0
        score = match_ratio * 2.0 + coverage * 0.5 + cal_fit * 0.3 + affinity_bonus + fav_bonus
        scored.append((score, rec, quantity, macros, match_ratio, missing_names))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        PantryRecipeMatchOut(
            slug=rec.slug, name=rec.name, tags=rec.tags, quantity=quantity, macros=macros,
            is_favorite=rec.is_favorite, match_ratio=round(match_ratio, 2), missing=missing_names,
        )
        for _, rec, quantity, macros, match_ratio, missing_names in scored[:limit]
    ]


def build_meal(
    session: Session, user: User, day: date, have_ids: list[int],
    meal_type: MealType | None = None, limit: int = 6,
) -> BuildMealOut:
    """'Montar refeicao com o que tenho em casa': terceira porta do motor, ao lado de
    suggest_gap/substitutes. Mesmos codigos de estado que o card do dia ja usa
    (no_goal/complete) - nao inventa um terceiro estado so pra esta tela."""
    goals = _daily_target(session, user.id)
    consumed = _consumed(session, user.id, day)
    if goals is None:
        return BuildMealOut(date=day, remaining=None, primary="no_goal")
    remaining = _remaining(goals, consumed)
    chosen = _choose_primary(remaining)
    if chosen is None:
        return BuildMealOut(date=day, remaining=remaining, primary="complete")

    have_set = set(have_ids)
    staple_ids = _staple_food_ids(session)
    freq = _food_frequency(session, user.id, day)
    max_freq = max(freq.values(), default=1)
    fav_ids = favorite_food_ids(session, user.id)
    meal_freq, max_meal_freq = None, 0
    if meal_type is not None:
        meal_freq = _meal_food_frequency(session, user.id, meal_type, day)
        max_meal_freq = max(meal_freq.values(), default=0)

    food_matches = _rank_suggestions(
        session, user, remaining, chosen[0], freq, max_freq, limit, fav_ids,
        restrict_ids=have_set | staple_ids,
        meal_freq=meal_freq, max_meal_freq=max_meal_freq,
        phase_food_ids=phase_boost_food_ids(session, user.id, day),
    )
    recipe_matches = match_pantry_recipes(session, user, remaining, have_set, meal_type, limit)
    return BuildMealOut(
        date=day, remaining=remaining, primary=chosen[1],
        recipe_matches=recipe_matches, food_matches=food_matches,
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
    freq = _food_frequency(session, user.id, day)
    max_freq = max(freq.values(), default=1)
    fav_ids = favorite_food_ids(session, user.id)
    # resolvido uma vez: a fase e a mesma para as quatro refeicoes do dia
    phase_ids = phase_boost_food_ids(session, user.id, day)
    # Com o bonus alto, o melhor alimento da fase venceria nas QUATRO refeicoes - o
    # cardapio viraria "feijao no cafe, no almoco, no lanche e na janta". Guardamos os
    # que ja foram usados pela fase para a proxima refeicao pegar o seguinte da lista.
    # So os da fase entram aqui: repeticao normal (arroz no almoco e na janta) e
    # legitima e continua permitida.
    phase_used: set[int] = set()

    meals: list[MealPlanMealOut] = []
    for meal_type, share in shares.items():
        target = _scale(goals, share)
        consumed_meal = _sum_entries([e for e in entries if e.meal_type == meal_type])
        meal_remaining = _bounded_remaining(target, consumed_meal, remaining_day)
        chosen = _choose_primary(meal_remaining)
        meal_freq = _meal_food_frequency(session, user.id, meal_type, day)
        max_meal_freq = max(meal_freq.values(), default=0)
        suggestions = (
            _rank_suggestions(
                session, user, meal_remaining, chosen[0], freq, max_freq, limit, fav_ids,
                meal_freq=meal_freq, max_meal_freq=max_meal_freq,
                phase_food_ids=phase_ids, exclude_ids=phase_used,
            )
            if chosen is not None
            else []
        )
        phase_used.update(s.food.id for s in suggestions if s.from_phase)
        recipe_suggestions = suggest_recipes(session, user, meal_remaining, meal_type)
        meals.append(
            MealPlanMealOut(
                meal_type=meal_type,
                target=target,
                consumed=consumed_meal,
                remaining=meal_remaining,
                primary=chosen[1] if chosen else "complete",
                suggestions=suggestions,
                recipe_suggestions=recipe_suggestions,
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
    freq = _food_frequency(session, user.id, date.today())
    fav_ids = favorite_food_ids(session, user.id)

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
        if cand.id in fav_ids:  # favorito puxa mais forte que seu/frequente
            distance *= 0.7
        ranked.append((distance, cand, cand_grams, cand_macros, kcal_delta))

    ranked.sort(key=lambda item: item[0])
    items = [
        SubstituteItemOut(
            food=to_food_out(cand, user.locale, fav_ids),
            grams=grams_, macros=macros, kcal_delta=delta,
        )
        for _, cand, grams_, macros, delta in ranked[:limit]
    ]
    return SubstitutesOut(
        source=SubstituteSourceOut(
            food=to_food_out(food, user.locale, fav_ids), grams=grams, macros=source_macros
        ),
        anchor=_ANCHOR_CODE.get(anchor, "calories"),
        items=items,
    )
