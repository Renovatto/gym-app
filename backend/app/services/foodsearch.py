"""Busca externa de alimentos (fase 5) via Open Food Facts - base aberta e gratuita.

Retorna candidatos com macros por 100 g; o usuario revisa e salva no catalogo dele
pelo fluxo normal de criar alimento. Falha de rede/timeout devolve lista vazia (o app
nunca trava por causa disso)."""

import time

import httpx

from ..schemas import ExternalFoodOut

# Busca TEXTUAL (CGI). O /api/v2/search ignora search_terms (devolvia sempre a mesma
# lista); o cgi/search.pl faz a busca por texto de verdade.
_OFF_URL = "https://world.openfoodfacts.org/cgi/search.pl"
_TIMEOUT = 8.0
# Open Food Facts pede um User-Agent identificavel nas chamadas de API.
_HEADERS = {"User-Agent": "GymApp/0.1 (personal fitness app)"}
# O OFF e instavel (rate limit/timeout ocasional): 1 nova tentativa evita que uma
# falha transitoria vire "nada encontrado" para o usuario.
_MAX_ATTEMPTS = 2
_RETRY_DELAY_S = 0.6


def _num(value: object) -> float:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return 0.0


def search_external(query: str, limit: int = 15, lang: str = "en") -> list[ExternalFoodOut]:
    term = query.strip()
    if not term:
        return []
    # lc = idioma da resposta (nomes localizados); pedimos o nome no idioma do usuario
    # e o nome padrao como fallback.
    localized_field = f"product_name_{lang}"
    params = {
        "search_terms": term,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "fields": f"product_name,{localized_field},brands,nutriments",
        "lc": lang,
        "page_size": limit,
    }
    products: list[dict] = []
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = httpx.get(_OFF_URL, params=params, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            products = resp.json().get("products", [])
            break
        except Exception:
            # rede/timeout/resposta invalida (comum no OFF): tenta mais uma vez antes
            # de desistir, para nao trocar uma falha transitoria por "nada encontrado"
            if attempt == _MAX_ATTEMPTS:
                return []
            time.sleep(_RETRY_DELAY_S)

    out: list[ExternalFoodOut] = []
    for product in products:
        # prefere o nome no idioma do usuario; cai pro nome padrao se nao houver
        name = (product.get(localized_field) or product.get("product_name") or "").strip()
        nutriments = product.get("nutriments") or {}
        kcal = nutriments.get("energy-kcal_100g")
        # sem nome ou sem caloria por 100 g nao serve (dado incompleto)
        if not name or kcal is None:
            continue
        brand = (product.get("brands") or "").split(",")[0].strip() or None
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
