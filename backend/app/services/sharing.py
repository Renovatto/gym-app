"""Copiar receita e alimento de uma conta para outra.

Por que copia e nao referencia: uma receita aponta para alimentos por food_id, e um
desses pode ser um alimento PESSOAL de quem enviou. Todo caminho de leitura do app
filtra alimento por "global OU meu" (Food.user_id IS NULL OR Food.user_id == eu) - na
busca, no motor de recomendacao, no "o que falta hoje", nos substitutos e no "montar
refeicao com o que tenho". Compartilhar por referencia obrigaria a reescrever esse
filtro em todos eles. Copiando, a duplicata nasce ja pertencendo a quem recebeu e
nenhuma consulta existente muda.
"""

from sqlmodel import Session, select

from ..models import (
    DiaryEntry,
    EntrySource,
    Food,
    FoodPortion,
    FoodTranslation,
    Profile,
    Recipe,
    RecipeIngredient,
    ShareOffer,
    ShareOfferMealItem,
    SharedItem,
    SharedItemKind,
    User,
)
from .diet import food_macros, localized_food_name, recipe_entry_macros, recipe_grams_per_serving
from .deduplication import food_content_key, lock_content, recipe_content_key


class SourceItemGone(Exception):
    """O original mudou (ou sumiu) na conta de quem enviou entre a oferta e o aceite."""


def _record_shared_item(
    session: Session,
    owner_user_id: int,
    item_kind: SharedItemKind,
    item_id: int,
    source_item_id: int,
    from_user_id: int,
) -> None:
    """Mantem a origem mesmo quando um item de conteudo igual e reaproveitado."""
    existing_link = session.exec(
        select(SharedItem)
        .where(SharedItem.owner_user_id == owner_user_id)
        .where(SharedItem.item_kind == item_kind)
        .where(SharedItem.item_id == item_id)
        .where(SharedItem.source_item_id == source_item_id)
        .where(SharedItem.from_user_id == from_user_id)
    ).first()
    if existing_link is not None:
        return
    session.add(
        SharedItem(
            owner_user_id=owner_user_id,
            item_kind=item_kind,
            item_id=item_id,
            source_item_id=source_item_id,
            from_user_id=from_user_id,
        )
    )


def display_name(session: Session, user_id: int) -> str:
    """Nome de quem esta do outro lado. Cai no e-mail quando a pessoa nao preencheu
    o perfil - melhor mostrar algo identificavel do que um espaco vazio."""
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if profile is not None:
        full_name = " ".join(filter(None, [profile.first_name, profile.last_name])).strip()
        if full_name:
            return full_name
    user = session.get(User, user_id)
    return user.email if user is not None else ""


def copy_food(session: Session, source: Food, to_user: User, from_user_id: int) -> int:
    """Devolve o id do alimento a usar na conta de quem recebeu.

    Alimento do catalogo global e o mesmo para todo mundo, entao nao se copia: basta
    reaproveitar o id. So alimento pessoal (user_id preenchido) vira copia."""
    if source.user_id is None:
        return source.id
    content_key = food_content_key(source)
    lock_content(session, to_user.id, "food", content_key)
    existing_foods = session.exec(
        select(Food).where(Food.user_id == to_user.id).where(Food.archived_at.is_(None))
    ).all()
    for existing_food in existing_foods:
        if food_content_key(existing_food) == content_key:
            _record_shared_item(
                session, to_user.id, SharedItemKind.food, existing_food.id,
                source.id, from_user_id,
            )
            return existing_food.id

    copy = Food(
        # slug marca a origem para nao colidir com um alimento que a pessoa ja tenha
        # criado com o mesmo nome
        slug=f"custom-{to_user.id}-shared-{source.id}",
        category=source.category,
        kcal=source.kcal,
        protein_g=source.protein_g,
        carbs_g=source.carbs_g,
        fat_g=source.fat_g,
        default_portion_g=source.default_portion_g,
        user_id=to_user.id,
    )
    session.add(copy)
    session.flush()
    # o nome vive nas traducoes: sem copiar, o alimento chegaria sem nome
    for translation in source.translations:
        session.add(
            FoodTranslation(food_id=copy.id, locale=translation.locale, name=translation.name)
        )
    for portion in source.portions:
        session.add(
            FoodPortion(food_id=copy.id, label_key=portion.label_key, grams=portion.grams)
        )
    _record_shared_item(
        session, to_user.id, SharedItemKind.food, copy.id, source.id, from_user_id
    )
    return copy.id


def copy_recipe(session: Session, source: Recipe, to_user: User, from_user_id: int) -> Recipe:
    """Copia a receita e, junto, os alimentos pessoais de que ela depende."""
    content_key = recipe_content_key(session, source)
    lock_content(session, to_user.id, "recipe", content_key)
    existing_recipes = session.exec(
        select(Recipe).where(Recipe.user_id == to_user.id).where(Recipe.archived_at.is_(None))
    ).all()
    for existing_recipe in existing_recipes:
        if recipe_content_key(session, existing_recipe) == content_key:
            _record_shared_item(
                session, to_user.id, SharedItemKind.recipe, existing_recipe.id,
                source.id, from_user_id,
            )
            return existing_recipe

    copy = Recipe(user_id=to_user.id, name=source.name, servings=source.servings)
    session.add(copy)
    session.flush()
    ingredients_to_copy: list[tuple[str, float, RecipeIngredient]] = []
    for ingredient in source.ingredients:
        source_food = session.get(Food, ingredient.food_id)
        if source_food is None:
            raise SourceItemGone
        ingredients_to_copy.append(
            (food_content_key(source_food), ingredient.grams, ingredient)
        )
    # A ordem fixa evita deadlock quando receitas diferentes compartilham varios alimentos.
    for _, _, ingredient in sorted(ingredients_to_copy, key=lambda item: (item[0], item[1])):
        food = session.get(Food, ingredient.food_id)
        assert food is not None
        session.add(
            RecipeIngredient(
                recipe_id=copy.id,
                food_id=copy_food(session, food, to_user, from_user_id),
                grams=ingredient.grams,
            )
        )
    _record_shared_item(
        session, to_user.id, SharedItemKind.recipe, copy.id, source.id, from_user_id
    )
    return copy


# --- Refeicao -------------------------------------------------------------


def freeze_meal_items(session: Session, offer: ShareOffer, entries: list[DiaryEntry]) -> None:
    """Guarda os lancamentos da refeicao como estao AGORA, presos a oferta.

    Se quem enviou mexer na refeicao depois, quem recebe continua ganhando o que foi
    enviado - e nao uma versao que ela nunca viu."""
    for entry in entries:
        session.add(
            ShareOfferMealItem(
                offer_id=offer.id,
                source=entry.source,
                food_id=entry.food_id,
                recipe_id=entry.recipe_id,
                quantity=entry.quantity,
                kcal=entry.kcal,
            )
        )


def _received_entry(
    session: Session, item: ShareOfferMealItem, offer: ShareOffer, to_user: User
) -> DiaryEntry:
    """Lancamento na conta de quem recebeu, calculado como se ela mesma tivesse lancado.

    Nome e macros sao recalculados (e nao copiados do lancamento de quem enviou)
    porque o nome guardado esta no idioma de quem enviou, e porque o alimento pessoal
    agora e a copia dela. Quantidade entra igual: ela ajusta depois se comeu outra."""
    if item.source == EntrySource.food:
        source_food = session.get(Food, item.food_id) if item.food_id is not None else None
        if source_food is None or source_food.user_id not in (None, offer.from_user_id):
            raise SourceItemGone
        food = session.get(Food, copy_food(session, source_food, to_user, offer.from_user_id))
        macros = food_macros(food, item.quantity)
        return DiaryEntry(
            user_id=to_user.id,
            entry_date=offer.meal_date,
            meal_type=offer.meal_type,
            source=EntrySource.food,
            food_id=food.id,
            quantity=item.quantity,
            grams=item.quantity,  # alimento ja e lancado em gramas
            name_snapshot=localized_food_name(food, to_user.locale),
            kcal=macros.kcal,
            protein_g=macros.protein_g,
            carbs_g=macros.carbs_g,
            fat_g=macros.fat_g,
        )

    source_recipe = session.get(Recipe, item.recipe_id) if item.recipe_id is not None else None
    if source_recipe is None or source_recipe.user_id != offer.from_user_id:
        raise SourceItemGone
    recipe = copy_recipe(session, source_recipe, to_user, offer.from_user_id)
    session.flush()  # a copia precisa dos ingredientes no banco para calcular macros
    session.refresh(recipe)
    macros = recipe_entry_macros(session, recipe, to_user.locale, item.quantity)
    # gramas = porcoes x peso de uma porcao (mesma conversao do lancamento normal)
    per_serving_g = recipe_grams_per_serving(recipe)
    return DiaryEntry(
        user_id=to_user.id,
        entry_date=offer.meal_date,
        meal_type=offer.meal_type,
        source=EntrySource.recipe,
        recipe_id=recipe.id,
        quantity=item.quantity,
        grams=round(per_serving_g * item.quantity, 1) if per_serving_g > 0 else None,
        name_snapshot=recipe.name,
        kcal=macros.kcal,
        protein_g=macros.protein_g,
        carbs_g=macros.carbs_g,
        fat_g=macros.fat_g,
    )


def accept_meal(session: Session, offer: ShareOffer, to_user: User) -> None:
    """Lanca a refeicao no diario de quem recebeu, no MESMO dia e refeicao de quem
    enviou, e marca cada lancamento com a origem (o selo "Recebido de Fulana").

    Tudo ou nada: se um item sumiu, SourceItemGone sobe e quem chamou desfaz o resto -
    uma refeicao pela metade deixaria o total do dia errado sem ninguem perceber."""
    items = session.exec(
        select(ShareOfferMealItem)
        .where(ShareOfferMealItem.offer_id == offer.id)
        .order_by(ShareOfferMealItem.id)
    ).all()
    for item in items:
        entry = _received_entry(session, item, offer, to_user)
        session.add(entry)
        session.flush()
        session.add(
            SharedItem(
                owner_user_id=to_user.id,
                item_kind=SharedItemKind.diary_entry,
                item_id=entry.id,
                # a oferta e a origem: o lancamento de quem enviou pode ter mudado ou
                # sumido depois do envio
                source_item_id=offer.id,
                from_user_id=offer.from_user_id,
            )
        )


def received_from_names(session: Session, user_id: int, entry_ids: list[int]) -> dict[int, str]:
    """Nome de quem enviou, por lancamento recebido. Uma consulta para o dia inteiro."""
    if not entry_ids:
        return {}
    links = session.exec(
        select(SharedItem)
        .where(SharedItem.owner_user_id == user_id)
        .where(SharedItem.item_kind == SharedItemKind.diary_entry)
        .where(SharedItem.item_id.in_(entry_ids))
    ).all()
    names: dict[int, str] = {}
    out: dict[int, str] = {}
    for link in links:
        if link.from_user_id not in names:
            names[link.from_user_id] = display_name(session, link.from_user_id)
        out[link.item_id] = names[link.from_user_id]
    return out


def forget_received_entry(session: Session, user_id: int, entry_id: int) -> None:
    """Tira o selo junto com o lancamento apagado - senao sobra vinculo orfao."""
    link = session.exec(
        select(SharedItem)
        .where(SharedItem.owner_user_id == user_id)
        .where(SharedItem.item_kind == SharedItemKind.diary_entry)
        .where(SharedItem.item_id == entry_id)
    ).first()
    if link is not None:
        session.delete(link)
