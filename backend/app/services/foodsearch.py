"""Busca externa de alimentos via Open Food Facts - base aberta e gratuita.

Retorna candidatos com macros por 100 g; o usuario revisa e salva no catalogo dele
pelo fluxo normal de criar alimento.

QUAL ENDPOINT E POR QUE
Usamos o servico de busca novo (search.openfoodfacts.org). O antigo cgi/search.pl
respondia HTML de erro na maior parte das vezes: medindo com cinco termos comuns, ele
trouxe resultado em 1 de 5, contra 5 de 5 do novo. Pior que ser lento, ele FALHAVA de
um jeito silencioso - buscar "amendoim" devolvia zero, e a pessoa concluia que o
produto nao existia na base quando na verdade a busca nunca rodou (o mesmo termo
dentro de uma frase maior funcionava, o que denunciava a inconsistencia).

O /api/v2/search tambem nao serve: ele ignora busca textual e devolve sempre a mesma
lista.

FALHA NAO E "NADA ENCONTRADO"
Por isso este modulo LEVANTA excecao quando a busca nao roda, em vez de devolver lista
vazia. Sao coisas diferentes para quem esta olhando a tela, e tratar as duas igual foi
o que escondeu o problema acima por tanto tempo.
"""

import time

import httpx

from ..schemas import ExternalFoodOut

_OFF_URL = "https://search.openfoodfacts.org/search"
# Busca por codigo de barras e outro servico: o codigo E a chave primaria da base,
# entao a consulta e exata e nao passa pelo indice de texto (que e o instavel).
_OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}"
_TIMEOUT = 10.0
# Open Food Facts pede um User-Agent identificavel nas chamadas de API.
_HEADERS = {"User-Agent": "GymApp/0.1 (personal fitness app)"}
# Uma nova tentativa cobre a instabilidade ocasional sem deixar a tela esperando.
_MAX_ATTEMPTS = 2
_RETRY_DELAY_S = 0.6


class ExternalSearchUnavailable(Exception):
    """A busca externa nao pode ser feita agora (rede, timeout, resposta invalida).

    Diferente de "a busca rodou e nao achou nada" - e por isso que existe."""


def _num(value: object) -> float:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return 0.0


def _to_food(product: dict, localized_field: str) -> ExternalFoodOut | None:
    """Converte um produto do OFF no nosso formato, ou None se vier inaproveitavel.

    Sem nome ou sem caloria por 100 g o cadastro na base esta incompleto e o item
    nao serve para importar - a pessoa veria um alimento com macros zeradas."""
    name = (product.get(localized_field) or product.get("product_name") or "").strip()
    nutriments = product.get("nutriments") or {}
    kcal = nutriments.get("energy-kcal_100g")
    if not name or kcal is None:
        return None
    # "brands" vem como lista no servico de busca e como string separada por virgula
    # no de produto; aceitamos os dois para nao quebrar se a base mudar de novo
    brands = product.get("brands") or []
    if isinstance(brands, str):
        brands = brands.split(",")
    brand = next((b.strip() for b in brands if b and b.strip()), None)
    return ExternalFoodOut(
        name=name,
        brand=brand,
        kcal=_num(kcal),
        protein_g=_num(nutriments.get("proteins_100g")),
        carbs_g=_num(nutriments.get("carbohydrates_100g")),
        fat_g=_num(nutriments.get("fat_100g")),
    )


def fetch_by_barcode(code: str, lang: str = "en") -> ExternalFoodOut | None:
    """Le um produto pelo codigo de barras. None = codigo nao existe na base.

    Atencao ao formato da resposta: o OFF devolve HTTP 200 tambem para codigo
    inexistente, com "status": 0 no corpo. Confiar no codigo HTTP aqui faria o app
    tratar "nao existe" como sucesso e mostrar um alimento vazio."""
    digits = code.strip()
    if not digits.isdigit():
        return None

    params = {"fields": f"product_name,product_name_{lang},brands,nutriments"}
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = httpx.get(
                _OFF_PRODUCT_URL.format(code=digits),
                params=params,
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            break
        except Exception as error:
            if attempt == _MAX_ATTEMPTS:
                raise ExternalSearchUnavailable(str(error)) from error
            time.sleep(_RETRY_DELAY_S)

    if payload.get("status") != 1:
        return None
    return _to_food(payload.get("product") or {}, f"product_name_{lang}")


def search_external(query: str, limit: int = 15, lang: str = "en") -> list[ExternalFoodOut]:
    term = query.strip()
    if not term:
        return []

    # pedimos o nome no idioma do usuario e o nome padrao como reserva
    localized_field = f"product_name_{lang}"
    # Pedimos MAIS que o limite porque cerca de 1 em 5 produtos da base vem sem tabela
    # nutricional (nutriments nulo) e e descartado logo abaixo. Sem essa folga, uma
    # pagina de 15 chegava com 3 itens aproveitaveis.
    params = {
        "q": term,
        "fields": f"product_name,{localized_field},brands,nutriments",
        "page_size": min(limit * 3, 90),
    }

    hits: list[dict] = []
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = httpx.get(_OFF_URL, params=params, headers=_HEADERS, timeout=_TIMEOUT)
            response.raise_for_status()
            hits = response.json().get("hits", [])
            break
        except Exception as error:
            if attempt == _MAX_ATTEMPTS:
                raise ExternalSearchUnavailable(str(error)) from error
            time.sleep(_RETRY_DELAY_S)

    out: list[ExternalFoodOut] = []
    for product in hits:
        food = _to_food(product, localized_field)
        if food is not None:
            out.append(food)
    return out
