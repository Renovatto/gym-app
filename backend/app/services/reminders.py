"""Lembretes de refeicao, pesagem e sequencia de treinos.

Dois caminhos usam as mesmas regras:
- dentro do app: a tela inicial pergunta "tem refeicao atrasada?" e mostra o cartao;
- com o app fechado: um laco no servidor olha, minuto a minuto, quem tem lembrete
  vencido e manda push (so para quem ligou em Perfil > Lembretes).

O "horario de costume" de cada refeicao e aprendido do proprio diario, nunca
perguntado: e a mediana do horario em que a pessoa costuma lancar aquela refeicao.
Sem historico suficiente o app simplesmente nao avisa - lembrar na hora errada e pior
que nao lembrar.
"""

import asyncio
import logging
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, desc, func, select

from ..db import engine
from ..models import (
    DiaryEntry,
    MealType,
    Profile,
    PushSubscription,
    ReminderLog,
    User,
    WeightLog,
    WorkoutSession,
)
from .achievements import STREAK_WEEK_GOAL, same_iso_week, weekly_streak_and_best
from .push import send_push

logger = logging.getLogger(__name__)

# So as 3 refeicoes principais tem lembrete. As extras (pre/pos-treino, ceia) e o
# lanche nao tem horario estavel o bastante para "passou do horario" fazer sentido.
REMINDER_MEALS: tuple[MealType, ...] = (MealType.breakfast, MealType.lunch, MealType.dinner)

# Janela para aprender o horario de costume: 2 semanas pegam a rotina de dia util e
# de fim de semana sem carregar habito antigo demais.
HABIT_WINDOW_DAYS = 14
# Dias com a refeicao lancada NA HORA necessarios para confiar no horario aprendido.
MIN_HABIT_DAYS = 5
# Folga depois do horario de costume antes de avisar: atrasar meia hora o almoco e
# normal, 1 hora ja indica esquecimento.
MEAL_GRACE_MINUTES = 60
# Passada essa janela depois da folga, o push da refeicao ja nao sai (servidor fora
# do ar, deploy): "ja almocou?" as 17h so irrita.
MEAL_PUSH_WINDOW_MINUTES = 120

# Pesagem: avisa a partir de 3 dias sem balanca, uma vez a cada 3 dias, de manha
# (a melhor hora de pesar e ao acordar, em jejum).
WEIGH_IN_GAP_DAYS = 3
WEIGH_IN_HOUR = 7

# Sequencia: sabado de manha e o ultimo momento em que ainda da para salvar a semana
# (sobram sabado e domingo). Segunda = 0 no weekday() do Python.
STREAK_REMINDER_WEEKDAY = 5
STREAK_REMINDER_HOUR = 10
DAYS_LEFT_ON_STREAK_DAY = 2  # sabado + domingo

# Silencio noturno e teto diario: lembrete demais vira ruido e a pessoa desliga tudo.
QUIET_START_HOUR = 22
QUIET_END_HOUR = 7
MAX_REMINDERS_PER_DAY = 3

# O laco nao precisa de precisao de segundos: lembrete com 1 minuto de atraso e igual.
POLL_INTERVAL_SECONDS = 60
# Quanto tempo o servico de push segura o lembrete com o aparelho offline.
REMINDER_TTL_SECONDS = 60 * 60


def meal_code(meal_type: MealType) -> str:
    return f"meal_{meal_type.value}"


def resolve_zone(time_zone: str | None) -> ZoneInfo | None:
    """Fuso IANA valido, ou None. Fuso invalido vindo do aparelho nao pode derrubar o
    laco de todo mundo."""
    if not time_zone:
        return None
    try:
        return ZoneInfo(time_zone)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def offset_converter(tz_offset: int) -> Callable[[datetime], datetime]:
    """UTC (sem fuso, como vem do banco) -> hora local, pelo tz_offset das telas
    (Date.getTimezoneOffset(): minutos que faltam para o UTC, positivo a oeste)."""
    return lambda utc_naive: utc_naive - timedelta(minutes=tz_offset)


def zone_converter(zone: ZoneInfo) -> Callable[[datetime], datetime]:
    """UTC (sem fuso, como vem do banco) -> hora local pelo fuso IANA guardado."""
    return lambda utc_naive: (
        utc_naive.replace(tzinfo=timezone.utc).astimezone(zone).replace(tzinfo=None)
    )


def minutes_of_day(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


def usual_meal_minutes(
    session: Session,
    user_id: int,
    meal_type: MealType,
    today: date,
    to_local: Callable[[datetime], datetime],
) -> int | None:
    """Horario de costume (minutos desde a meia-noite local) de uma refeicao.

    Para cada dia da janela pega o PRIMEIRO lancamento daquela refeicao, e so conta o
    dia se ele foi lancado no proprio dia: quem lanca o almoco de ontem hoje cedo
    puxaria o "horario do almoco" para 8h. A janela termina ONTEM - hoje ainda esta
    em andamento e e justamente o dia que esta sendo avaliado.

    Mediana e nao media: um dia atipico (almoco as 16h no domingo) nao arrasta o
    horario de todos os outros.
    """
    window_start = today - timedelta(days=HABIT_WINDOW_DAYS)
    rows = session.exec(
        select(DiaryEntry.entry_date, DiaryEntry.logged_at)
        .where(DiaryEntry.user_id == user_id)
        .where(DiaryEntry.meal_type == meal_type)
        .where(DiaryEntry.entry_date >= window_start)
        .where(DiaryEntry.entry_date < today)
    ).all()

    first_log_by_day: dict[date, datetime] = {}
    for entry_date, logged_at in rows:
        local_logged_at = to_local(logged_at)
        if local_logged_at.date() != entry_date:
            continue  # lancado em outro dia: nao diz nada sobre o horario da refeicao
        current_first = first_log_by_day.get(entry_date)
        if current_first is None or local_logged_at < current_first:
            first_log_by_day[entry_date] = local_logged_at

    if len(first_log_by_day) < MIN_HABIT_DAYS:
        return None
    return int(statistics.median_low(minutes_of_day(t) for t in first_log_by_day.values()))


def _codes_logged_today(session: Session, user_id: int, today: date) -> dict[str, str]:
    """Lembretes ja resolvidos hoje: codigo -> outcome ("sent" | "skipped")."""
    rows = session.exec(
        select(ReminderLog.code, ReminderLog.outcome)
        .where(ReminderLog.user_id == user_id)
        .where(ReminderLog.local_date == today)
    ).all()
    return {code: outcome for code, outcome in rows}


def _meal_logged_on(session: Session, user_id: int, meal_type: MealType, day: date) -> bool:
    return (
        session.exec(
            select(DiaryEntry.id)
            .where(DiaryEntry.user_id == user_id)
            .where(DiaryEntry.meal_type == meal_type)
            .where(DiaryEntry.entry_date == day)
        ).first()
        is not None
    )


@dataclass(frozen=True)
class OverdueMeal:
    meal_type: MealType
    usual_minutes: int


def overdue_meals(
    session: Session,
    user_id: int,
    today: date,
    now_local: datetime,
    to_local: Callable[[datetime], datetime],
) -> list[OverdueMeal]:
    """Refeicoes principais que ja passaram do horario de costume + folga e ainda nao
    foram lancadas hoje. A que a pessoa marcou como "Pulei hoje" fica de fora."""
    handled_today = _codes_logged_today(session, user_id, today)
    now_minutes = minutes_of_day(now_local)
    result: list[OverdueMeal] = []
    for meal_type in REMINDER_MEALS:
        if handled_today.get(meal_code(meal_type)) == "skipped":
            continue
        usual = usual_meal_minutes(session, user_id, meal_type, today, to_local)
        if usual is None or now_minutes < usual + MEAL_GRACE_MINUTES:
            continue
        if _meal_logged_on(session, user_id, meal_type, today):
            continue
        result.append(OverdueMeal(meal_type, usual))
    return result


def days_since_last_weigh_in(
    session: Session, user_id: int, today: date, to_local: Callable[[datetime], datetime]
) -> int | None:
    latest = session.exec(
        select(WeightLog.logged_at)
        .where(WeightLog.user_id == user_id)
        .order_by(desc(WeightLog.logged_at))
    ).first()
    if latest is None:
        return None
    return (today - to_local(latest).date()).days


@dataclass(frozen=True)
class StreakRisk:
    streak_weeks: int  # semanas seguidas ja garantidas (antes desta)
    workouts_missing: int  # treinos que faltam para esta semana contar


def streak_at_risk(
    session: Session, user_id: int, today: date, to_local: Callable[[datetime], datetime]
) -> StreakRisk | None:
    """Sequencia em risco: existe sequencia, a semana atual ainda nao bateu a meta e
    ainda da tempo de bater (faltam no maximo os dias que sobram). Semana que ja nao
    tem salvacao nao gera aviso - lembrar de algo impossivel so desanima."""
    finished_at_values = session.exec(
        select(WorkoutSession.finished_at)
        .where(WorkoutSession.user_id == user_id)
        .where(WorkoutSession.finished_at.is_not(None))
    ).all()
    workout_days = [to_local(finished_at).date() for finished_at in finished_at_values]
    streak, _best_week = weekly_streak_and_best(workout_days, today)
    workouts_this_week = sum(1 for d in workout_days if same_iso_week(d, today))
    # treinos que faltam = meta da semana - feitos (nunca negativo)
    workouts_missing = max(0, STREAK_WEEK_GOAL - workouts_this_week)
    if streak == 0 or workouts_missing == 0 or workouts_missing > DAYS_LEFT_ON_STREAK_DAY:
        return None
    return StreakRisk(streak_weeks=streak, workouts_missing=workouts_missing)


# --- Push (laco de fundo) ---------------------------------------------------


@dataclass(frozen=True)
class DueReminder:
    code: str
    url: str
    params: dict = field(default_factory=dict)


def _in_quiet_hours(now_local: datetime) -> bool:
    return now_local.hour >= QUIET_START_HOUR or now_local.hour < QUIET_END_HOUR


def due_reminders(
    session: Session, user: User, profile: Profile, now_local: datetime, zone: ZoneInfo
) -> list[DueReminder]:
    """Lembretes que devem sair AGORA para esta pessoa, ja respeitando silencio
    noturno, teto diario e o que ja saiu hoje."""
    if _in_quiet_hours(now_local):
        return []
    today = now_local.date()
    to_local = zone_converter(zone)
    handled_today = _codes_logged_today(session, user.id, today)
    sent_today = sum(1 for outcome in handled_today.values() if outcome == "sent")
    if sent_today >= MAX_REMINDERS_PER_DAY:
        return []

    due: list[DueReminder] = []
    now_minutes = minutes_of_day(now_local)

    if profile.reminder_meals and profile.diet_enabled:
        for meal in overdue_meals(session, user.id, today, now_local, to_local):
            if meal_code(meal.meal_type) in handled_today:
                continue
            # so dentro da janela logo depois da folga (ver MEAL_PUSH_WINDOW_MINUTES)
            if now_minutes > meal.usual_minutes + MEAL_GRACE_MINUTES + MEAL_PUSH_WINDOW_MINUTES:
                continue
            due.append(
                DueReminder(
                    code=meal_code(meal.meal_type),
                    url=f"/dieta/adicionar?meal={meal.meal_type.value}",
                    params={"meal": meal.meal_type.value, "usual_minutes": meal.usual_minutes},
                )
            )

    if profile.reminder_weigh_in and now_local.hour >= WEIGH_IN_HOUR:
        days = days_since_last_weigh_in(session, user.id, today, to_local)
        recently_reminded = session.exec(
            select(func.count(ReminderLog.id))
            .where(ReminderLog.user_id == user.id)
            .where(ReminderLog.code == "weigh_in")
            .where(ReminderLog.local_date > today - timedelta(days=WEIGH_IN_GAP_DAYS))
        ).one()
        if days is not None and days >= WEIGH_IN_GAP_DAYS and recently_reminded == 0:
            due.append(DueReminder(code="weigh_in", url="/progresso?novo=1", params={"days": days}))

    if (
        profile.reminder_streak
        and now_local.weekday() == STREAK_REMINDER_WEEKDAY
        and now_local.hour >= STREAK_REMINDER_HOUR
        and "streak" not in handled_today
    ):
        risk = streak_at_risk(session, user.id, today, to_local)
        if risk is not None:
            due.append(
                DueReminder(
                    code="streak",
                    url="/treino",
                    params={"streak": risk.streak_weeks, "missing": risk.workouts_missing},
                )
            )

    return due[: MAX_REMINDERS_PER_DAY - sent_today]


def _claim(session: Session, user_id: int, code: str, local_date: date) -> bool:
    """Registra o envio ANTES de enviar. Se outro worker ja registrou (chave unica),
    nao insere nada e este nao envia - o mesmo aviso nunca sai duas vezes."""
    inserted_id = session.execute(
        pg_insert(ReminderLog.__table__)
        .values(
            user_id=user_id,
            code=code,
            local_date=local_date,
            outcome="sent",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        .on_conflict_do_nothing(index_elements=["user_id", "code", "local_date"])
        .returning(ReminderLog.__table__.c.id)
    ).scalar_one_or_none()
    session.commit()
    return inserted_id is not None


def _deliver_due_reminders() -> None:
    with Session(engine) as session:
        # So quem ligou algum lembrete, tem fuso conhecido e tem aparelho inscrito.
        candidates = session.exec(
            select(User, Profile)
            .join(Profile, Profile.user_id == User.id)
            .where(
                Profile.reminder_meals | Profile.reminder_weigh_in | Profile.reminder_streak
            )
            .where(Profile.time_zone.is_not(None))
            .where(
                select(PushSubscription.id)
                .where(PushSubscription.user_id == User.id)
                .exists()
            )
        ).all()
        for user, profile in candidates:
            zone = resolve_zone(profile.time_zone)
            if zone is None:
                continue
            now_local = datetime.now(zone).replace(tzinfo=None)
            try:
                reminders = due_reminders(session, user, profile, now_local, zone)
            except Exception:
                # dado estranho de uma pessoa nao pode parar os lembretes das outras
                logger.exception("falha ao avaliar lembretes do usuario %s", user.id)
                session.rollback()
                continue
            for reminder in reminders:
                if not _claim(session, user.id, reminder.code, now_local.date()):
                    continue
                payload = {
                    "kind": "reminder",
                    "code": reminder.code,
                    # o texto e montado no service worker, no idioma da pessoa (a API
                    # nunca manda texto de interface pronto)
                    "locale": user.locale.lower(),
                    "params": reminder.params,
                    "url": reminder.url,
                }
                subscriptions = session.exec(
                    select(PushSubscription).where(PushSubscription.user_id == user.id)
                ).all()
                for subscription in subscriptions:
                    send_push(session, subscription, payload, ttl_seconds=REMINDER_TTL_SECONDS)


async def run_reminder_loop() -> None:
    """Laco de fundo dos lembretes (iniciado no lifespan do main.py), no mesmo molde
    do laco do descanso: o envio bloqueia, entao roda numa thread."""
    while True:
        try:
            await asyncio.to_thread(_deliver_due_reminders)
        except Exception:
            logger.exception("falha no laco de lembretes")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
