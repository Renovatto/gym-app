"""Envio de e-mail. Por enquanto e um STUB de desenvolvimento: apenas imprime o
conteudo no log do servidor (nao ha provedor de e-mail configurado ainda).

No deploy (Render), trocar send_password_reset_email por um envio real via provedor
(ex.: Resend, SendGrid) usando as credenciais em variaveis de ambiente. A assinatura
da funcao fica igual, entao o resto do codigo nao muda."""

from ..config import settings


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    # Link que o usuario abriria para redefinir a senha (a pagina existe no frontend).
    reset_link = f"{settings.frontend_url}/redefinir-senha?token={reset_token}"
    # STUB: em producao, aqui entra a chamada ao provedor de e-mail.
    print("=" * 60)
    print(f"[email stub] Para: {to_email}")
    print("[email stub] Assunto: Redefinir sua senha")
    print(f"[email stub] Link de redefinicao: {reset_link}")
    print("=" * 60)
