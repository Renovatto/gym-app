"""Novidades do app: o que mudou e por que isso importa para quem usa.

Duas decisoes que explicam o formato do dado:

1. **O texto vive no banco, nos tres idiomas.** Foge da regra geral do projeto (string
   de UI vira chave em messages/*.json e a API devolve codigo, nunca texto pronto). O
   motivo e que aqui o texto e escrito em tempo de execucao, no painel admin - nao ha
   chave para o paraglide compilar. E conteudo, nao interface.
2. **A traducao e resolvida no servidor**, pelo user.locale, igual ao nome de alimento
   (services/diet.py). O cliente recebe um titulo e um corpo ja no idioma dele.

Criterio editorial (vale mais que qualquer codigo aqui): novidade se escreve quando a
resposta a "isso muda o que o app diz para a pessoa fazer?" for sim. Ajuste de layout
nao vira novidade; correcao que mexe na meta calorica, sim.
"""

from ..models import NewsItem

# Quando o idioma do usuario nao tem texto preenchido, cai no portugues: e o idioma em
# que as novidades sao escritas, entao e o unico que sempre existe de fato.
FALLBACK_LOCALE = "pt-BR"

_BY_LOCALE = {
    "pt-BR": ("title_pt_br", "body_pt_br"),
    "en": ("title_en", "body_en"),
    "es": ("title_es", "body_es"),
}


def localized_news(item: NewsItem, locale: str) -> tuple[str, str]:
    """Titulo e corpo da novidade no idioma do usuario, com fallback no portugues."""
    title_field, body_field = _BY_LOCALE.get(locale, _BY_LOCALE[FALLBACK_LOCALE])
    title = getattr(item, title_field).strip()
    body = getattr(item, body_field).strip()
    if not title or not body:
        title_field, body_field = _BY_LOCALE[FALLBACK_LOCALE]
        title = getattr(item, title_field)
        body = getattr(item, body_field)
    return title, body
