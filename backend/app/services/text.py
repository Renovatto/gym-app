"""Normalização de texto para buscas: minúsculas e sem acentos.

Padrão do sistema: TODA busca textual deve comparar valores passados por
normalize_search dos dois lados (termo e alvo), para que "pao" encontre "Pão".
"""

import unicodedata


def normalize_search(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))
