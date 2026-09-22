"""Envio de e-mail transacional via SMTP.

Sem `GYMAPP_SMTP_USER` configurado, cai num STUB que apenas imprime o conteudo no
log do servidor. E o modo de desenvolvimento: ninguem precisa de credencial para
rodar o projeto localmente, e o link de redefinicao aparece no terminal.

Em producao as credenciais vem do `.env` (ver `config.py`). Hoje usamos SMTP do
Gmail com "senha de app" - nao a senha da conta.

Todo e-mail (hoje so a redefinicao de senha, mas qualquer envio futuro) usa a
mesma casca visual em `_render_email_html`: faixa escura com o logo do app,
cartao branco com o conteudo. Reaproveitar essa funcao mantem a marca
consistente sem copiar HTML de e-mail em cada lugar novo que precisar mandar
uma mensagem.
"""

import smtplib
import logging
from email.message import EmailMessage

from ..config import settings

logger = logging.getLogger(__name__)

# Tempo maximo esperando o servidor SMTP. Sem limite, uma indisponibilidade do
# provedor penduraria o worker que atende a requisicao.
SMTP_TIMEOUT_SECONDS = 15

# Mesma pilha do app (Tailwind v4 usa ui-sans-serif/system-ui como font-sans
# padrao, e o projeto nao carrega fonte propria), com os nomes explicitos atras:
# leitor de e-mail que nao conhece ui-sans-serif/system-ui cai em Times se nao
# achar nenhuma familia com nome de verdade na lista.
_FONT_STACK = (
    "ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
)

# Hex equivalentes dos tokens do app. O Tailwind v4 declara as cores em oklch, que
# leitor de e-mail nao entende - aqui vao as mesmas cores ja convertidas para sRGB.
_EMERALD_600 = "#009966"  # acao primaria, igual ao bg-emerald-600 dos botoes
_SLATE_900 = "#0f172a"  # faixa escura e titulo; hardcoded assim no favicon/manifest
_SLATE_500 = "#62748e"  # texto de apoio
_SLATE_400 = "#90a1b9"  # rodape
_SLATE_200 = "#e2e8f0"  # linha divisoria
_SLATE_50 = "#f8fafc"  # fundo da pagina

# Textos por idioma, espelhando os locales suportados no frontend
# (messages/{pt-br,en,es}.json). A API nunca devolve texto pronto, mas e-mail e
# conteudo final para uma pessoa ler, entao aqui o texto e montado no backend.
_PASSWORD_RESET_TEXTS = {
    "pt-br": {
        "subject": "Redefinir sua senha",
        "intro": "Voce pediu para redefinir sua senha no Gym App.",
        "plain_lead": "Abra o link abaixo para escolher uma nova senha:",
        "cta": "Redefinir senha",
        "validity": "O link vale por {minutes} minutos.",
        "ignore": "Se nao foi voce quem pediu, ignore este e-mail: sua senha continua a mesma.",
        "fallback_lead": "Se o botao nao funcionar, copie e cole este link no navegador:",
    },
    "en": {
        "subject": "Reset your password",
        "intro": "You asked to reset your Gym App password.",
        "plain_lead": "Open the link below to choose a new password:",
        "cta": "Reset password",
        "validity": "The link is valid for {minutes} minutes.",
        "ignore": "If you did not request this, ignore this email: your password is unchanged.",
        "fallback_lead": "If the button does not work, copy and paste this link into your browser:",
    },
    "es": {
        "subject": "Restablecer tu contrasena",
        "intro": "Solicitaste restablecer tu contrasena en Gym App.",
        "plain_lead": "Abre el enlace de abajo para elegir una nueva contrasena:",
        "cta": "Restablecer contrasena",
        "validity": "El enlace es valido por {minutes} minutos.",
        "ignore": "Si no fuiste tu, ignora este correo: tu contrasena sigue igual.",
        "fallback_lead": "Si el boton no funciona, copia y pega este enlace en tu navegador:",
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


def _render_email_html(
    heading: str,
    paragraphs: list[str],
    button_text: str,
    button_url: str,
    footnote: str,
    ignore_note: str,
    link_fallback_lead: str,
) -> str:
    """Casca de e-mail reaproveitada por qualquer envio transacional (Opcao A do
    material de design aprovado: faixa escura com o logo, cartao branco com o
    conteudo). Tudo em tabela com estilo inline - e o unico jeito de nao quebrar
    no Outlook e no Gmail, que ignoram flexbox/grid e boa parte do CSS externo.
    Por isso tambem nao reproduz o anel de progresso nem a sobreposicao na
    costura da maquete original: sao efeitos que dependem de recursos (SVG
    animado, position:absolute) que a maioria dos leitores de e-mail descarta.
    """
    # email-logo.png, e nao icon-192/512.png: o icone do app tem ~35% de fundo
    # vazio acima e abaixo do halter, desenhado dentro da propria imagem. Como
    # esse fundo e o mesmo #0f172a da faixa, ele some visualmente e vira
    # distancia - que cresce junto com a imagem e afasta o nome do app quanto
    # maior o logo. email-logo.png e o mesmo desenho recortado no halter, entao
    # o tamanho da imagem e o tamanho do que se ve, e o respiro vem so do HTML.
    logo_url = f"{settings.frontend_url}/email-logo.png"
    # 16px/slate-500: mesmo corpo de texto da tela de recuperar senha no app
    paragraphs_html = "".join(
        f'<tr><td align="center" style="padding:0 0 16px;font-family:{_FONT_STACK};'
        f'font-size:16px;line-height:26px;color:{_SLATE_500};">{p}</td></tr>'
        for p in paragraphs
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading}</title>
</head>
<body style="margin:0;padding:0;background-color:{_SLATE_50};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_SLATE_50};">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#ffffff;border-radius:20px;">
<tr>
<td align="center" valign="middle" height="136" style="background-color:{_SLATE_900};padding:0 24px;border-radius:20px 20px 0 0;font-size:0;line-height:0;">
<!--
  Tabela aninhada em vez de img+span soltos: texto solto entre tags vira espaco
  em branco com a altura de linha padrao do navegador e se soma ao espacador.
  font-size/line-height:0 em cada td anula esse espaco invisivel, entao a unica
  distancia entre o halter e o nome e o height da linha do meio.
--><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
<td align="center" style="font-size:0;line-height:0;"><img src="{logo_url}" width="145" height="75" alt="Gym App" style="display:block;border:0;"></td>
</tr><tr>
<td align="center" height="10" style="font-size:0;line-height:10px;">&nbsp;</td>
</tr><tr>
<td align="center" style="font-size:0;line-height:0;"><span style="font-family:{_FONT_STACK};font-size:13px;line-height:13px;font-weight:700;letter-spacing:4px;color:{_SLATE_200};text-transform:uppercase;">Gym App</span></td>
</tr></table>
</td>
</tr>
<tr>
<td style="padding:40px 40px 8px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:0 0 18px;"><h1 style="margin:0;font-family:{_FONT_STACK};font-size:24px;line-height:30px;font-weight:900;letter-spacing:-0.6px;color:{_SLATE_900};">{heading}</h1></td></tr>
{paragraphs_html}
<tr><td align="center" style="padding:8px 0 4px;">
<table role="presentation" cellpadding="0" cellspacing="0">
<tr><td align="center" style="background-color:{_EMERALD_600};border-radius:16px;">
<a href="{button_url}" style="display:inline-block;padding:17px 40px;font-family:{_FONT_STACK};font-size:18px;line-height:22px;font-weight:700;color:#ffffff;text-decoration:none;">{button_text}</a>
</td></tr>
</table>
</td></tr>
<tr><td align="center" style="padding:14px 0 4px;"><p style="margin:0;font-family:{_FONT_STACK};font-size:14px;line-height:20px;color:{_SLATE_500};">{footnote}</p></td></tr>
<tr><td style="padding:24px 0 0;"><div style="border-top:1px solid {_SLATE_200};font-size:1px;line-height:1px;">&nbsp;</div></td></tr>
<tr><td align="center" style="padding:20px 0 4px;"><p style="margin:0;font-family:{_FONT_STACK};font-size:12px;line-height:18px;color:{_SLATE_400};">Gym App &middot; rgymapp.duckdns.org<br>{ignore_note}</p></td></tr>
<tr><td align="center" style="padding:12px 0 32px;"><p style="margin:0;font-family:{_FONT_STACK};font-size:12px;line-height:18px;color:{_SLATE_400};word-break:break-all;">{link_fallback_lead}<br><a href="{button_url}" style="color:{_SLATE_500};">{button_url}</a></p></td></tr>
</table>
</td>
</tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _enviar(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    """Entrega uma mensagem multipart (texto + HTML) pelo SMTP configurado.

    set_content + add_alternative monta o multipart/alternative sozinho: quem
    le em texto puro fica com text_body, quem tem cliente com HTML ve a versao
    formatada.
    """
    mensagem = EmailMessage()
    mensagem["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    mensagem["To"] = to_email
    mensagem["Subject"] = subject
    mensagem.set_content(text_body)
    mensagem.add_alternative(html_body, subtype="html")

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
    validity = textos["validity"].format(minutes=settings.password_reset_minutes)

    text_body = (
        f"{textos['intro']}\n\n"
        f"{textos['plain_lead']}\n{reset_link}\n\n"
        f"{validity}\n\n"
        f"{textos['ignore']}"
    )
    html_body = _render_email_html(
        heading=subject,
        paragraphs=[textos["intro"]],
        button_text=textos["cta"],
        button_url=reset_link,
        footnote=validity,
        ignore_note=textos["ignore"],
        link_fallback_lead=textos["fallback_lead"],
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
        _enviar(to_email, subject, text_body, html_body)
    except Exception:
        # exception() registra o traceback completo no log do servico, que e onde
        # da para investigar depois (journalctl -u gymapp.service).
        logger.exception("Falha ao enviar e-mail de redefinicao de senha")
