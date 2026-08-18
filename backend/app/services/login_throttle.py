"""Freio de forca bruta no login: conta as tentativas que falharam e tranca a
chave por um tempo quando ela passa do limite.

Duas chaves sao contadas em paralelo, porque sao dois ataques diferentes:

- por **conta** (e-mail): alguem martelando senha numa conta especifica;
- por **IP**: alguem tentando a mesma senha comum em MUITAS contas diferentes -
  ai nenhum e-mail sozinho chega ao limite, mas o IP chega.
"""

import ipaddress
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlmodel import Session, select

from ..models import LoginAttempt

# Janela de contagem: falhas mais velhas que isso nao contam mais e o contador
# recomeca do zero na proxima tentativa.
FAILURE_WINDOW = timedelta(minutes=15)
# Quanto tempo a chave fica trancada depois de estourar o limite.
BLOCK_DURATION = timedelta(minutes=15)
# Limite por conta. Baixo de proposito: cinco erros seguidos ja e sinal de que
# nao e a pessoa dona da conta tentando lembrar a senha.
MAX_FAILURES_PER_EMAIL = 5
# Limite por IP. Bem mais alto porque uma casa ou uma academia inteira pode sair
# do mesmo IP, e travar o IP trava todo mundo que esta atras dele.
MAX_FAILURES_PER_IP = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(moment: datetime) -> datetime:
    """datetime do SQLite volta sem fuso; tratamos como UTC para comparar."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def client_ip(request: Request) -> str | None:
    """IP de quem chamou, ou None quando nao da para distinguir um cliente do outro.

    Atras do nginx o IP real so chega se o proxy mandar X-Forwarded-For. Sem isso
    toda requisicao aparece como 127.0.0.1 e contar por IP travaria o app inteiro
    de uma vez - por isso o loopback devolve None e o freio por IP fica desligado.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # O ultimo item da lista e o que o nginx enxergou de verdade; os anteriores
        # podem ter sido forjados por quem chamou.
        candidate = forwarded.split(",")[-1].strip()
    else:
        candidate = request.client.host if request.client else ""

    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return None if address.is_loopback else candidate


def _keys_with_limits(email: str, ip: str | None) -> list[tuple[str, int]]:
    """Chaves a contar nesta tentativa, cada uma com o proprio limite."""
    keys = [(f"email:{email.lower()}", MAX_FAILURES_PER_EMAIL)]
    if ip is not None:
        keys.append((f"ip:{ip}", MAX_FAILURES_PER_IP))
    return keys


def _find(session: Session, key: str) -> LoginAttempt | None:
    return session.exec(select(LoginAttempt).where(LoginAttempt.key == key)).first()


def blocked_seconds(session: Session, email: str, ip: str | None) -> int:
    """Segundos que ainda faltam do bloqueio, ou 0 quando pode tentar.

    Se as duas chaves estiverem trancadas, vale a que solta por ultimo."""
    remaining = 0
    for key, _limit in _keys_with_limits(email, ip):
        record = _find(session, key)
        if record is None or record.blocked_until is None:
            continue
        seconds_left = (_as_utc(record.blocked_until) - _now()).total_seconds()
        remaining = max(remaining, int(seconds_left))
    return max(remaining, 0)


def register_failure(session: Session, email: str, ip: str | None) -> None:
    """Soma uma falha na conta e no IP, trancando a chave que passar do limite."""
    now = _now()
    for key, limit in _keys_with_limits(email, ip):
        record = _find(session, key)
        if record is None:
            record = LoginAttempt(key=key, failures=0, window_started_at=now)
        # Janela vencida: o que aconteceu ha muito tempo nao pesa mais contra quem
        # errou a senha hoje.
        if now - _as_utc(record.window_started_at) > FAILURE_WINDOW:
            record.failures = 0
            record.window_started_at = now
            record.blocked_until = None
        record.failures += 1
        if record.failures >= limit:
            record.blocked_until = now + BLOCK_DURATION
        session.add(record)
    session.commit()


def clear_failures(session: Session, email: str) -> None:
    """Login deu certo: zera a contagem da conta.

    O contador do IP continua de proposito - se ele tambem zerasse, bastaria a
    quem ataca entrar na propria conta de tempos em tempos para limpar a ficha."""
    record = _find(session, f"email:{email.lower()}")
    if record is None:
        return
    session.delete(record)
    session.commit()
