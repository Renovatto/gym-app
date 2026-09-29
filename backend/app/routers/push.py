from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ..config import settings
from ..deps import CurrentUser, SessionDep
from ..models import PushSubscription, RestTimerPush, WorkoutSession
from ..schemas import PushPublicKeyOut, PushSubscriptionIn, PushUnsubscribeIn, RestTimerPushIn
from ..services.push import push_enabled, utc_now_naive

router = APIRouter(tags=["push"])


@router.get("/push/public-key", response_model=PushPublicKeyOut)
def public_key() -> PushPublicKeyOut:
    """Chave publica VAPID que o navegador precisa para assinar. Sem login: e publica
    por definicao, e o app pede antes de saber se vai assinar."""
    return PushPublicKeyOut(public_key=settings.vapid_public_key if push_enabled() else "")


@router.put("/me/push/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def save_subscription(payload: PushSubscriptionIn, user: CurrentUser, session: SessionDep) -> None:
    """Registra (ou atualiza) o aparelho. Idempotente: o app chama a cada abertura do
    treino, e o mesmo endpoint so muda de chaves ou de dono, nunca duplica."""
    subscription = session.exec(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    ).first()
    if subscription is None:
        subscription = PushSubscription(
            user_id=user.id,
            endpoint=payload.endpoint,
            p256dh_key=payload.p256dh,
            auth_secret=payload.auth,
        )
    else:
        subscription.user_id = user.id
        subscription.p256dh_key = payload.p256dh
        subscription.auth_secret = payload.auth
    session.add(subscription)
    session.commit()


@router.post("/me/push/subscriptions/remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_subscription(payload: PushUnsubscribeIn, user: CurrentUser, session: SessionDep) -> None:
    """Esquece o aparelho (ex.: ao sair da conta). POST e nao DELETE porque o endpoint
    e uma URL longa que vai no corpo, nao no caminho."""
    subscription = session.exec(
        select(PushSubscription)
        .where(PushSubscription.endpoint == payload.endpoint)
        .where(PushSubscription.user_id == user.id)
    ).first()
    if subscription is not None:
        session.delete(subscription)
        session.commit()


@router.put("/me/push/rest-timer", status_code=status.HTTP_204_NO_CONTENT)
def schedule_rest_timer(payload: RestTimerPushIn, user: CurrentUser, session: SessionDep) -> None:
    """Agenda o aviso de fim do descanso. Chamado ao iniciar o descanso e de novo a
    cada "+30s": sempre substitui o agendamento anterior do usuario."""
    workout = session.get(WorkoutSession, payload.workout_session_id)
    if workout is None or workout.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SESSION_NOT_FOUND")

    send_at = utc_now_naive() + timedelta(seconds=payload.seconds_remaining)
    timer = session.exec(select(RestTimerPush).where(RestTimerPush.user_id == user.id)).first()
    if timer is None:
        timer = RestTimerPush(
            user_id=user.id,
            workout_session_id=workout.id,
            send_at=send_at,
            title=payload.title,
            body=payload.body,
        )
    else:
        timer.workout_session_id = workout.id
        timer.send_at = send_at
        timer.title = payload.title
        timer.body = payload.body
    session.add(timer)
    session.commit()


@router.delete("/me/push/rest-timer", status_code=status.HTTP_204_NO_CONTENT)
def cancel_rest_timer(user: CurrentUser, session: SessionDep) -> None:
    """Cancela o aviso pendente (descanso pulado, treino encerrado, ou o descanso
    acabou com o app aberto e a propria tela ja avisou)."""
    timer = session.exec(select(RestTimerPush).where(RestTimerPush.user_id == user.id)).first()
    if timer is not None:
        session.delete(timer)
        session.commit()
