"""Publica novidades no app a partir de um arquivo JSON.

Existe porque toda subida leva uma novidade nos tres idiomas: sao seis campos por
entrada, e digitar isso no painel a cada release e onde o passo costuma ser pulado.

    GYMAPP_ADMIN_TOKEN=... python tools/publicar_novidades.py tools/novidades_X.json

O token e o mesmo que o painel usa: abra o /admin logado e copie
localStorage.getItem('gymapp.access') do console. Ele fica so no seu ambiente - o
script le da variavel e nunca o escreve em lugar nenhum.

Por padrao aponta para producao; use --api para outro destino (ex.: o backend local
em http://localhost:8765). Antes de enviar, o script MOSTRA o que vai publicar e
pede confirmacao: novidade publicada aparece para todo mundo na proxima abertura.
"""

import argparse
import json
import os
import sys
from urllib import error, request

API_PADRAO = "https://rgymapp.duckdns.org/api"
CAMPOS = (
    "published_on",
    "title_pt_br",
    "body_pt_br",
    "title_en",
    "body_en",
    "title_es",
    "body_es",
)


def carregar(caminho: str) -> list[dict]:
    with open(caminho, encoding="utf-8") as arquivo:
        entradas = json.load(arquivo)
    if not isinstance(entradas, list):
        raise SystemExit("o arquivo precisa ser uma LISTA de novidades")
    # Validacao aqui, antes de mandar: a API recusaria de qualquer jeito, mas o erro
    # dela chega uma entrada por vez - e a terceira so falharia depois das duas
    # primeiras ja estarem publicadas.
    for i, entrada in enumerate(entradas, 1):
        faltando = [campo for campo in CAMPOS if not entrada.get(campo)]
        if faltando:
            raise SystemExit(f"novidade {i}: faltam os campos {', '.join(faltando)}")
    return entradas


def publicar(api: str, token: str, entrada: dict) -> dict:
    corpo = json.dumps(entrada).encode("utf-8")
    pedido = request.Request(
        f"{api.rstrip('/')}/admin/news",
        data=corpo,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with request.urlopen(pedido, timeout=20) as resposta:
        return json.loads(resposta.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica novidades a partir de um JSON")
    parser.add_argument("arquivo", help="JSON com a lista de novidades")
    parser.add_argument("--api", default=os.environ.get("GYMAPP_API_URL", API_PADRAO))
    args = parser.parse_args()

    token = os.environ.get("GYMAPP_ADMIN_TOKEN", "").strip()
    if not token:
        raise SystemExit("defina GYMAPP_ADMIN_TOKEN (veja o cabecalho deste arquivo)")

    entradas = carregar(args.arquivo)

    print(f"\nDestino: {args.api}")
    print(f"{len(entradas)} novidade(s) a publicar:\n")
    for i, entrada in enumerate(entradas, 1):
        print(f"  {i}. [{entrada['published_on']}] {entrada['title_pt_br']}")
        print(f"     {entrada['body_pt_br'][:90]}...")
    try:
        resposta = input("\nPublicar? Isso aparece para todos os usuarios. [s/N] ")
    except EOFError:
        # sem terminal (pipe, CI): nao ha como confirmar, entao nao publica
        resposta = ""
    if resposta.strip().lower() != "s":
        print("cancelado.")
        return

    for i, entrada in enumerate(entradas, 1):
        try:
            criada = publicar(args.api, token, entrada)
        except error.HTTPError as erro:
            detalhe = erro.read().decode("utf-8", "replace")[:200]
            print(f"  {i}. FALHOU ({erro.code}): {detalhe}", file=sys.stderr)
            print("     as anteriores ja foram publicadas; corrija e rode so o que faltou.")
            raise SystemExit(1) from None
        print(f"  {i}. publicada (id {criada.get('id')})")

    print("\npronto.")


if __name__ == "__main__":
    main()
