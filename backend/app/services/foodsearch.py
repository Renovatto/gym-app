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
        name = (product.get(localized_field) or product.get("product_name") or "").strip()
        nutriments = product.get("nutriments") or {}
        kcal = nutriments.get("energy-kcal_100g")
        # sem nome ou sem caloria por 100 g nao serve (cadastro incompleto na base)
        if not name or kcal is None:
            continue
        # "brands" vem como lista neste endpoint (era string separada por virgula no
        # antigo); aceitamos os dois para nao quebrar se a base mudar de novo
        brands = product.get("brands") or []
        if isinstance(brands, str):
            brands = brands.split(",")
        brand = next((b.strip() for b in brands if b and b.strip()), None)
        out.append(
            ExternalFoodOut(
                name=name,
                brand=brand,
                kcal=_num(kcal),
                protein_g=_num(nutriments.get("proteins_100g")),
                carbs_g=_num(nutriments.get("carbohydrates_100g")),
                fat_g=_num(nutriments.get("fat_100g")),
            )
        )
    return out
