"""Envio de e-mail transacional via SMTP.

Sem `GYMAPP_SMTP_USER` configurado, cai num STUB que apenas imprime o conteudo no
log do servidor. E o modo de desenvolvimento: ninguem precisa de credencial para
rodar o projeto localmente, e o link de redefinicao aparece no terminal.

Em producao as credenciais vem do `.env` (ver `config.py`). Hoje usamos SMTP do
Gmail com "senha de app" - nao a senha da conta.
"""

import smtplib
import logging
from email.message import EmailMessage

from ..config import settings

logger = logging.getLogger(__name__)

# Tempo maximo esperando o servidor SMTP. Sem limite, uma indisponibilidade do
# provedor penduraria o worker que atende a requisicao.
SMTP_TIMEOUT_SECONDS = 15

# Textos por idioma, espelhando os locales suportados no frontend
# (messages/{pt-br,en,es}.json). A API nunca devolve texto pronto, mas e-mail e
# conteudo final para uma pessoa ler, entao aqui o texto e montado no backend.
_PASSWORD_RESET_TEXTS = {
    "pt-br": {
        "subject": "Redefinir sua senha",
        "body": (
            "Voce pediu para redefinir sua senha no Gym App.\n\n"
            "Abra o link abaixo para escolher uma nova senha:\n"
            "{link}\n\n"
            "O link vale por {minutes} minutos.\n\n"
            "Se nao foi voce quem pediu, ignore este e-mail: sua senha continua a mesma."
        ),
    },
    "en": {
        "subject": "Reset your password",
        "body": (
            "You asked to reset your Gym App password.\n\n"
            "Open the link below to choose a new password:\n"
            "{link}\n\n"
            "The link is valid for {minutes} minutes.\n\n"
            "If you did not request this, ignore this email: your password is unchanged."
        ),
    },
    "es": {
        "subject": "Restablecer tu contrasena",
        "body": (
            "Solicitaste restablecer tu contrasena en Gym App.\n\n"
            "Abre el enlace de abajo para elegir una nueva contrasena:\n"
            "{link}\n\n"
            "El enlace es valido por {minutes} minutos.\n\n"
            "Si no fuiste tu, ignora este correo: tu contrasena sigue igual."
        ),
    },
}

_DEFAULT_LOCALE = "pt-br"


def _resolve_locale(locale: str | None) -> str:
    """Normaliza o locale do usuario para uma das chaves de texto disponiveis.

    O modelo guarda "pt-BR", os arquivos de traducao usam "pt-br", e um dia pode
    chegar so "pt". Cai no padrao em vez de quebrar o envio por causa do idioma.
    """
    if not locale:
        return _DEFAULT_LOCALE
    normalizado = locale.lower().replace("_", "-")
    if normalizado in _PASSWORD_RESET_TEXTS:
        return normalizado
    # "pt-PT" e "pt" caem em portugues; "en-US" cai em ingles.
    prefixo = normalizado.split("-")[0]
    for chave in _PASSWORD_RESET_TEXTS:
        if chave.split("-")[0] == prefixo:
            return chave
    return _DEFAULT_LOCALE


def _smtp_configurado() -> bool:
    return bool(settings.smtp_user and settings.smtp_password)


def _enviar(to_email: str, subject: str, body: str) -> None:
    """Entrega uma mensagem de texto simples pelo SMTP configurado."""
    mensagem = EmailMessage()
    mensagem["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    mensagem["To"] = to_email
    mensagem["Subject"] = subject
    mensagem.set_content(body)

    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
    ) as servidor:
        # STARTTLS: a conexao comeca em texto claro e e promovida para TLS. E o
        # que a porta 587 espera (a 465 usaria SMTP_SSL, TLS desde o inicio).
        servidor.starttls()
        servidor.login(settings.smtp_user, settings.smtp_password)
        servidor.send_message(mensagem)


def send_password_reset_email(
    to_email: str, reset_token: str, locale: str | None = None
) -> None:
    """Envia o link de redefinicao de senha.

    Nunca levanta excecao: o endpoint que chama esta funcao responde 202 mesmo
    quando o e-mail nao existe, justamente para nao revelar quem tem conta. Se uma
    falha de SMTP virasse erro 500, essa protecao cairia por terra - daria para
    descobrir quais e-mails estao cadastrados olhando o codigo de resposta.
    """
    # Link que o usuario abre para redefinir a senha (a pagina existe no frontend).
    reset_link = f"{settings.frontend_url}/redefinir-senha?token={reset_token}"
    textos = _PASSWORD_RESET_TEXTS[_resolve_locale(locale)]
    subject = textos["subject"]
    body = textos["body"].format(
        link=reset_link, minutes=settings.password_reset_minutes
    )

    if not _smtp_configurado():
        # STUB de desenvolvimento: sem credencial, o link vai para o log.
        print("=" * 60)
        print(f"[email stub] Para: {to_email}")
        print(f"[email stub] Assunto: {subject}")
        print(f"[email stub] Link de redefinicao: {reset_link}")
        print("=" * 60)
        return

    try:
        _enviar(to_email, subject, body)
    except Exception:
        # exception() registra o traceback completo no log do servico, que e onde
        # da para investigar depois (journalctl -u gymapp.service).
        logger.exception("Falha ao enviar e-mail de redefinicao de senha")
