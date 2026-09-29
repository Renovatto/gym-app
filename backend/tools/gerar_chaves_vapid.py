"""Gera o par de chaves VAPID do Web Push e imprime as linhas prontas para o .env.

VAPID (Voluntary Application Server Identification) = par de chaves que identifica
este servidor para os servicos de push. Gere UMA vez por ambiente: trocar a chave
invalida todas as assinaturas ja feitas (cada aparelho teria que assinar de novo).

Uso: .venv/bin/python tools/gerar_chaves_vapid.py
A chave privada e segredo: vai no .env, nunca no repositorio (ele e publico).
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def to_base64url(raw: bytes) -> str:
    # base64 "de URL" sem o preenchimento "=", formato que o navegador e o pywebpush esperam
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    # privada = o numero secreto de 32 bytes; publica = o ponto nao comprimido (65 bytes)
    private_raw = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    print(f"GYMAPP_VAPID_PUBLIC_KEY={to_base64url(public_raw)}")
    print(f"GYMAPP_VAPID_PRIVATE_KEY={to_base64url(private_raw)}")


if __name__ == "__main__":
    main()
