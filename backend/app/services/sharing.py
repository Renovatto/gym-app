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
    Food,
    FoodPortion,
    FoodTranslation,
    Recipe,
    RecipeIngredient,
    SharedItem,
    SharedItemKind,
    User,
)


class SourceItemGone(Exception):
    """O original mudou (ou sumiu) na conta de quem enviou entre a oferta e o aceite."""


def _existing_copy_id(
    session: Session,
    owner_user_id: int,
    kind: SharedItemKind,
    source_item_id: int,
    from_user_id: int,
) -> int | None:
    """Id da copia que ja existe para esse mesmo original, se houver.

    Sem isso, aceitar cinco receitas que usam o mesmo alimento pessoal criaria cinco
    copias do alimento na conta de quem recebeu."""
    return session.exec(
        select(SharedItem.item_id)
        .where(SharedItem.owner_user_id == owner_user_id)
        .where(SharedItem.item_kind == kind)
        .where(SharedItem.source_item_id == source_item_id)
        .where(SharedItem.from_user_id == from_user_id)
    ).first()


def copy_food(session: Session, source: Food, to_user: User, from_user_id: int) -> int:
    """Devolve o id do alimento a usar na conta de quem recebeu.

    Alimento do catalogo global e o mesmo para todo mundo, entao nao se copia: basta
    reaproveitar o id. So alimento pessoal (user_id preenchido) vira copia."""
    if source.user_id is None:
        return source.id
    already = _existing_copy_id(
        session, to_user.id, SharedItemKind.food, source.id, from_user_id
    )
    if already is not None:
        return already

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
    session.add(
        SharedItem(
            owner_user_id=to_user.id,
            item_kind=SharedItemKind.food,
            item_id=copy.id,
            source_item_id=source.id,
            from_user_id=from_user_id,
        )
    )
    return copy.id


def copy_recipe(session: Session, source: Recipe, to_user: User, from_user_id: int) -> Recipe:
    """Copia a receita e, junto, os alimentos pessoais de que ela depende."""
    already = _existing_copy_id(
        session, to_user.id, SharedItemKind.recipe, source.id, from_user_id
    )
    if already is not None:
        existing = session.get(Recipe, already)
        if existing is not None:
            return existing

    copy = Recipe(user_id=to_user.id, name=source.name, servings=source.servings)
    session.add(copy)
    session.flush()
    for ingredient in source.ingredients:
        food = session.get(Food, ingredient.food_id)
        if food is None:
            # Preferimos falhar a entregar uma receita silenciosamente sem ingrediente:
            # os macros ficariam errados sem ninguem perceber. Quem enviou pode
            # compartilhar de novo depois de arrumar a receita.
            raise SourceItemGone
        session.add(
            RecipeIngredient(
                recipe_id=copy.id,
                food_id=copy_food(session, food, to_user, from_user_id),
                grams=ingredient.grams,
            )
        )
    session.add(
        SharedItem(
            owner_user_id=to_user.id,
            item_kind=SharedItemKind.recipe,
            item_id=copy.id,
            source_item_id=source.id,
            from_user_id=from_user_id,
        )
    )
    return copy
