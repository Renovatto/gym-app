"""Categorias de alimento no padrao TACO

Revision ID: 4ffaac4be64c
Revises: 214a5232d394
Create Date: 2026-08-22 10:12:44.108227

As categorias antigas 'protein' e 'carb' eram nome de nutriente, nao de comida: o
usuario nao acha pao em "Carboidrato" e a troca equivalente do recommend.py chegava
a oferecer arroz no lugar do pao (mesmo macro, outro papel no prato). Esta migracao
adota os grupos da TACO (tabela brasileira de composicao de alimentos), quebrando
'protein' em carne/peixe/ovo, 'carb' em panificado/cereal/tuberculo e tirando as
oleaginosas de dentro de 'fat'.

Postgres nao remove valor de enum (nao existe DROP VALUE), entao 'protein' e 'carb'
continuam existindo no tipo apos a migracao, sem nenhuma linha usando. E so residuo
no catalogo do banco - o app nao os oferece mais.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4ffaac4be64c'
down_revision: Union[str, Sequence[str], None] = '214a5232d394'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_VALUES = (
    "bakery", "cereal_grain", "tuber", "meat", "seafood", "egg", "nuts_seeds",
    "sauce_condiment",
)

# Catalogo do app (user_id IS NULL) revisado item a item: aqui o slug decide, nao a
# categoria antiga - so assim ovo sai de 'protein' e batata sai de 'carb'.
CATALOG_BY_SLUG: dict[str, list[str]] = {
    "bakery": [
        "bread", "cheese-bread", "french-bread", "tapioca-cooked", "whole-wheat-bread"
    ],
    "cereal_grain": [
        "brown-rice", "cassava-flour-toasted", "corn", "corn-couscous", "cornmeal", "couscous",
        "fresh-lasagna-raw", "granola", "oats", "pasta", "polenta-precooked", "popcorn-oil",
        "potato-gnocchi", "quinoa", "seasoned-farofa", "tapioca-flour", "wheat-flour",
        "white-rice"
    ],
    "egg": [
        "boiled-egg", "egg", "egg-white", "egg-yolk-cooked", "fried-egg"
    ],
    "fat": [
        "butter", "coconut-oil", "olive-oil", "sunflower-oil"
    ],
    "meat": [
        "bacon", "beef-bottom-sirloin", "beef-chuck", "beef-flank", "beef-ribeye",
        "beef-rump-cap", "beef-shank", "beef-sirloin", "beef-tenderloin", "chicken-breast",
        "chicken-drumstick-thigh", "chicken-thigh", "chicken-wing", "ground-beef", "ham",
        "hot-dog-sausage", "iberian-ham", "iberian-pluma", "iberian-presa", "iberian-secreto",
        "lean-beef", "mortadella", "pork-belly", "pork-cheek", "pork-chop", "pork-leg",
        "pork-loin", "pork-ribs", "pork-sausage", "serrano-ham", "turkey-breast"
    ],
    "nuts_seeds": [
        "almonds", "avocado", "brazil-nut", "cashew", "chia", "flaxseed", "peanut",
        "peanut-butter", "walnuts"
    ],
    "sauce_condiment": [
        "salt", "tomato-paste", "tomato-sauce"
    ],
    "seafood": [
        "anchovy", "canned-tuna", "cod", "gilthead-bream", "hake", "salmon", "salmon-grilled",
        "salmon-raw", "sardine", "sardine-canned", "sea-bass", "shrimp", "shrimp-fried",
        "tilapia"
    ],
    "tuber": [
        "arracacha-cooked", "cassava", "cassava-fried", "cassava-raw", "potato",
        "potato-fried", "potato-raw", "sweet-potato", "sweet-potato-raw", "taro-cooked",
        "yam-raw"
    ],
}

# Alimento criado pelo usuario nao tem slug conhecido: cai no palpite que acerta a
# maioria. Ele pode reclassificar na tela do alimento quando quiser.
FALLBACK = {"protein": "meat", "carb": "cereal_grain"}

# Volta do downgrade: o grupo novo devolve o guarda-chuva de onde ele saiu. E uma
# volta aproximada - o que a migracao reclassificou por slug (panceta, molho de
# tomate) volta pelo grupo, nao para a categoria exata que tinha antes.
ROLLBACK = {
    "meat": "protein", "seafood": "protein", "egg": "protein",
    "bakery": "carb", "cereal_grain": "carb", "tuber": "carb",
    "nuts_seeds": "fat", "sauce_condiment": "other",
}


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _set_category(category: str, slugs: list[str]) -> None:
    """UPDATE do catalogo por slug.

    Os valores vao literais no SQL (e nao como parametro) de proposito: no Postgres a
    coluna e do tipo enum foodcategory e so um literal sem tipo recebe o cast implicito
    para o enum. Sao constantes deste arquivo, nunca entrada de usuario.
    """
    slug_list = ", ".join(f"'{slug}'" for slug in slugs)
    op.execute(
        f"UPDATE foods SET category = '{category}'"
        f" WHERE user_id IS NULL AND slug IN ({slug_list})"
    )


def upgrade() -> None:
    """Upgrade schema."""
    if _is_postgres():
        # Valor novo de enum precisa estar commitado antes de qualquer UPDATE usar.
        with op.get_context().autocommit_block():
            for value in NEW_VALUES:
                op.execute(f"ALTER TYPE foodcategory ADD VALUE IF NOT EXISTS '{value}'")

    for category, slugs in CATALOG_BY_SLUG.items():
        _set_category(category, slugs)

    for old, new in FALLBACK.items():
        op.execute(
            f"UPDATE foods SET category = '{new}'"
            f" WHERE CAST(category AS TEXT) = '{old}'"
        )


def downgrade() -> None:
    """Downgrade schema."""
    for new, old in ROLLBACK.items():
        # O CAST evita o erro do Postgres quando o valor comparado nem existe mais
        # no tipo enum - sem ele um downgrade fora de ordem quebra no WHERE.
        op.execute(
            f"UPDATE foods SET category = '{old}'"
            f" WHERE CAST(category AS TEXT) = '{new}'"
        )
