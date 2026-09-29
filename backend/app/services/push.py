"""Envio de notificacao push (Web Push) e o laco que dispara os avisos agendados.

Por que push do servidor: com o app em segundo plano o sistema congela o JavaScript
da tela (o iOS quase na hora), entao um timer no navegador nunca chega a avisar. Quem
avisa e o servidor, no horario marcado, e o service worker do aparelho mostra a
notificacao mesmo com o app fechado.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

from pywebpush import WebPushException, webpush
from sqlalchemy import Row, delete, select as sa_select
from sqlmodel import Session, select

from ..config import settings
from ..db import engine
from ..models import PushSubscription, RestTimerPush, utcnow

logger = logging.getLogger(__name__)

# De quanto em quanto tempo o laco procura aviso vencido. 1s e a precisao que um
# descanso de 60-180s pede; a consulta e trivial (indice em send_at).
POLL_INTERVAL_SECONDS = 1.0
# Aviso que venceu ha mais que isso (servidor fora do ar, deploy longo) e descartado:
# "descanso acabou" chegando 10 minutos depois so atrapalha.
STALE_AFTER = timedelta(minutes=2)
# Quanto tempo o servico de push segura a mensagem se o aparelho estiver offline.
# Curto pelo mesmo motivo do STALE_AFTER.
PUSH_TTL_SECONDS = 60


def utc_now_naive() -> datetime:
    """Agora em UTC sem fuso, o mesmo formato da coluna send_at (timestamp sem time
    zone). Comparar com um valor com fuso faria o Postgres converter pelo fuso da
    conexao, e o aviso sairia horas antes ou depois se ele nao fosse UTC."""
    return utcnow().replace(tzinfo=None)


def push_enabled() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def _vapid_subject() -> str:
    """Contato exigido pelo VAPID: so aceita "https:" ou "mailto:". Em producao o
    frontend_url ja e https; em dev (http://localhost) cai no e-mail do admin."""
    if settings.vapid_subject:
        return settings.vapid_subject
    if settings.frontend_url.startswith("https://"):
        return settings.frontend_url
    admin_email = settings.admin_emails[0] if settings.admin_emails else "admin@localhost"
    return f"mailto:{admin_email}"


def send_push(
    session: Session,
    subscription: PushSubscription,
    payload: dict,
    ttl_seconds: int = PUSH_TTL_SECONDS,
) -> None:
    """Envia uma mensagem para um aparelho. Assinatura que o servico de push diz que
    nao existe mais (404/410: app desinstalado, permissao revogada) e apagada."""
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh_key, "auth": subscription.auth_secret},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            # dict novo a cada envio: o pywebpush escreve aud/exp dentro dele
            vapid_claims={"sub": _vapid_subject()},
            ttl=ttl_seconds,
            # "high" pede entrega imediata mesmo com o aparelho em economia de bateria
            headers={"Urgency": "high"},
            timeout=10,
        )
    except WebPushException as error:
        status_code = error.response.status_code if error.response is not None else None
        if status_code in (404, 410):
            session.delete(subscription)
            session.commit()
            return
        logger.warning("push falhou (status %s): %s", status_code, error)
    except Exception:
        # erro inesperado (rede, chave mal configurada) num aparelho nao pode impedir
        # o envio para os outros aparelhos do mesmo usuario
        logger.exception("push falhou para a assinatura %s", subscription.id)


def _take_due_rest_timers(session: Session) -> list[Row]:
    """Tira da fila os avisos vencidos e os devolve, numa operacao so.

    DELETE ... RETURNING com SKIP LOCKED: com 2 workers rodando este laco, cada linha
    sai para exatamente um deles - nunca o mesmo aviso duas vezes. Devolve as colunas
    (e nao objetos do ORM) porque a linha ja nao existe mais depois do commit."""
    due_ids = (
        sa_select(RestTimerPush.id)
        .where(RestTimerPush.send_at <= utc_now_naive())
        .with_for_update(skip_locked=True)
    )
    rows = session.execute(
        delete(RestTimerPush)
        .where(RestTimerPush.id.in_(due_ids))
        .returning(
            RestTimerPush.user_id,
            RestTimerPush.workout_session_id,
            RestTimerPush.send_at,
            RestTimerPush.title,
            RestTimerPush.body,
        )
    ).all()
    session.commit()
    return list(rows)


def _deliver_due_rest_timers() -> None:
    with Session(engine) as session:
        for timer in _take_due_rest_timers(session):
            if utc_now_naive() - timer.send_at > STALE_AFTER:
                continue
            payload = {
                "kind": "rest_done",
                "title": timer.title,
                "body": timer.body,
                # tocar na notificacao volta para o treino que estava correndo
                "url": f"/treino/sessao/{timer.workout_session_id}",
            }
            subscriptions = session.exec(
                select(PushSubscription).where(PushSubscription.user_id == timer.user_id)
            ).all()
            for subscription in subscriptions:
                send_push(session, subscription, payload)


async def run_rest_timer_loop() -> None:
    """Laco de fundo que vive junto com a API (iniciado no lifespan do main.py).

    O envio e bloqueante (requests por baixo do pywebpush), entao roda numa thread
    para nao travar as outras requisicoes do worker."""
    while True:
        try:
            await asyncio.to_thread(_deliver_due_rest_timers)
        except Exception:
            # um erro de banco ou de rede nao pode matar o laco para sempre
            logger.exception("falha no laco de avisos de descanso")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
