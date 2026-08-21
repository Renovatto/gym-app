from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import asc, desc, select

from ..deps import CurrentUser, SessionDep
from ..models import (
    DiaryEntry,
    Objective,
    Profile,
    StandaloneActivity,
    WaterLog,
    WeightLog,
    WorkoutSession,
)
from ..schemas import AdaptiveTdeeOut, WeekSummaryOut
from ..services.adaptive import (
    ADAPTIVE_WINDOW_DAYS,
    MIN_DAYS_LOGGED,
    MIN_SPAN_DAYS,
    MIN_WEIGH_INS,
    estimate_maintenance,
)
from ..services.goals import (
    KCAL_PER_KG_FAT,
    WEEKLY_LOSS_RATE_PCT,
    basal_metabolic_rate,
    age_from_birthdate,
    compute_goals,
    target_calories_from_maintenance,
)
from ..services.dietplan import maintenance_override as diet_maintenance_override

router = APIRouter(prefix="/me/summary", tags=["stats"])


def _utc_window(start_day: date, end_day: date, tz_offset_min: int) -> tuple[datetime, datetime]:
    """Janela UTC cobrindo [start_day 00:00, end_day+1 00:00) no fuso local."""
    start_local = datetime.combine(start_day, time.min)
    end_local = datetime.combine(end_day + timedelta(days=1), time.min)
    start = (start_local + timedelta(minutes=tz_offset_min)).replace(tzinfo=timezone.utc)
    end = (end_local + timedelta(minutes=tz_offset_min)).replace(tzinfo=timezone.utc)
    return start, end


@router.get("/week", response_model=WeekSummaryOut)
def week_summary(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (dentro da semana)"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente"),
) -> WeekSummaryOut:
    # Semana do CALENDARIO, comecando na segunda, e nao os ultimos 7 dias. A tela diz
    # "Esta semana": com janela movel, abrir o app numa segunda mostrava desde a terca
    # anterior, ou seja, a semana passada. Segunda como inicio segue o isocalendar()
    # que as conquistas ja usam - as duas telas precisam contar a mesma semana.
    start_day = day - timedelta(days=day.weekday())
    start_utc, end_utc = _utc_window(start_day, day, tz_offset)

    # Treinos concluídos e volume na semana
    sessions = session.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .where(WorkoutSession.finished_at.is_not(None))
        .where(WorkoutSession.started_at >= start_utc)
        .where(WorkoutSession.started_at < end_utc)
    ).all()
    total_volume = 0.0
    total_sets = 0
    for ws in sessions:
        for s in ws.sets:
            if s.done:
                total_volume += s.reps * s.weight_kg
                total_sets += 1

    # Atividade avulsa (corrida, bike, ioga...) na mesma janela. entry_date ja e o dia
    # local do usuario, entao compara direto com os dias, sem converter fuso.
    activities = session.exec(
        select(StandaloneActivity)
        .where(StandaloneActivity.user_id == user.id)
        .where(StandaloneActivity.entry_date >= start_day)
        .where(StandaloneActivity.entry_date <= day)
    ).all()

    # Dias em movimento: dias distintos com treino OU atividade. Uniao, nao soma - um
    # dia de musculacao mais corrida conta uma vez so, senao o numero passaria de 7.
    workout_days = {(ws.started_at - timedelta(minutes=tz_offset)).date() for ws in sessions}
    activity_days = {a.entry_date for a in activities}
    active_dates = sorted(workout_days | activity_days)

    # Dieta: média de kcal por dia com registro (entry_date é dia local)
    diary = session.exec(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user.id)
        .where(DiaryEntry.entry_date >= start_day)
        .where(DiaryEntry.entry_date <= day)
    ).all()
    kcal_by_day: dict[date, float] = defaultdict(float)
    for e in diary:
        kcal_by_day[e.entry_date] += e.kcal
    days_logged = len(kcal_by_day)
    avg_kcal = round(sum(kcal_by_day.values()) / days_logged) if days_logged else 0

    # Água: média por dia com registro
    water = session.exec(
        select(WaterLog)
        .where(WaterLog.user_id == user.id)
        .where(WaterLog.logged_at >= start_utc)
        .where(WaterLog.logged_at < end_utc)
    ).all()
    ml_by_day: dict[date, int] = defaultdict(int)
    for w in water:
        local_dt = w.logged_at - timedelta(minutes=tz_offset)
        ml_by_day[local_dt.date()] += w.amount_ml
    days_water = len(ml_by_day)
    avg_water = round(sum(ml_by_day.values()) / days_water) if days_water else 0

    return WeekSummaryOut(
        workouts=len(sessions),
        active_days=len(active_dates),
        active_dates=active_dates,
        activities=len(activities),
        activities_kcal=round(sum(a.kcal for a in activities)),
        total_volume_kg=round(total_volume, 1),
        total_sets=total_sets,
        avg_kcal=avg_kcal,
        days_logged_diet=days_logged,
        avg_water_ml=avg_water,
        days_with_water=days_water,
    )


# Leituras que denunciam janela contaminada, cada uma por uma ponta da conta:
#   TOO_FAST           - a ponta da BALANCA. Perder rapido demais quase sempre e agua e
#                        glicogenio saindo, nao gordura. A conversao kg->kcal assume
#                        gordura, entao ali a manutencao estimada sai inflada.
#   MEASURED_BELOW_BMR - a ponta do DIARIO. Manutencao menor que o gasto em repouso e
#                        impossivel: ninguem gasta menos em movimento do que parado. O
#                        que aconteceu foi diario incompleto puxando a media para baixo.
# Nos dois casos o numero continua visivel (o usuario tem direito de ver o que os dados
# dele deram), mas nao pode virar meta.
UNRELIABLE_ESTIMATE_CODES = frozenset({"TOO_FAST", "MEASURED_BELOW_BMR"})


def _can_adopt_estimate(message_code: str, suggested_target_kcal: int | None) -> bool:
    """A estimativa e boa o bastante para o usuario adotar como meta?

    Adotar troca a meta calorica do app inteiro dali em diante, entao so liberamos
    quando ha dados suficientes E a leitura e plausivel (ver os codigos acima)."""
    if suggested_target_kcal is None:
        return False
    return message_code not in UNRELIABLE_ESTIMATE_CODES


def _adaptive_message_code(
    profile: Profile, weight_kg: float, weekly_change_kg: float
) -> str:
    """Escolhe a mensagem com base no ritmo real vs o desejado.
    weekly_change_kg negativo = perdendo peso."""
    if profile.objective != Objective.lose_fat:
        return "ESTIMATE_READY"
    # perda desejada por semana (kg, valor positivo) a partir da intensidade
    desired_weekly_loss = weight_kg * (WEEKLY_LOSS_RATE_PCT[profile.cut_intensity] / 100)
    actual_weekly_loss = -weekly_change_kg  # positivo se esta perdendo
    if actual_weekly_loss <= 0:
        return "STALLED"  # nao esta perdendo (ou ganhando)
    if actual_weekly_loss < 0.5 * desired_weekly_loss:
        return "TOO_SLOW"
    if actual_weekly_loss > 1.5 * desired_weekly_loss:
        return "TOO_FAST"
    return "ON_TRACK"


@router.get("/adaptive", response_model=AdaptiveTdeeOut)
def adaptive_tdee(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (fim da janela)"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente"),
) -> AdaptiveTdeeOut:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="PROFILE_NOT_FOUND")

    start_day = day - timedelta(days=ADAPTIVE_WINDOW_DAYS - 1)
    start_utc, end_utc = _utc_window(start_day, day, tz_offset)

    # Pesagens na janela viram pontos (indice_do_dia, peso) para a regressao.
    weight_logs = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user.id)
        .where(WeightLog.logged_at >= start_utc)
        .where(WeightLog.logged_at < end_utc)
        .order_by(asc(WeightLog.logged_at))
    ).all()
    weigh_ins: list[tuple[float, float]] = []
    for log in weight_logs:
        local_date = (log.logged_at - timedelta(minutes=tz_offset)).date()
        day_index = (local_date - start_day).days
        weigh_ins.append((float(day_index), log.weight_kg))

    # Peso mais recente e BMR: precisam vir ANTES da estimativa, porque o BMR e o que
    # define o piso de plausibilidade de um dia de diario (ver adaptive.py).
    latest_weight = session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user.id)
        .order_by(desc(WeightLog.logged_at), desc(WeightLog.id))
    ).first()
    weight_kg = latest_weight.weight_kg if latest_weight else (
        weigh_ins[-1][1] if weigh_ins else 0
    )
    age = age_from_birthdate(profile.birthdate)
    # Sem peso registrado nao ha BMR; 0 desliga os cortes que dependem dele.
    bmr = basal_metabolic_rate(weight_kg, profile.height_cm, age, profile.sex) if weight_kg else 0.0

    # Diario alimentar na janela: total de kcal por dia, terminando em ONTEM. O dia de
    # hoje esta sempre incompleto e entraria na media como um dia inteiro de pouca
    # comida, puxando a manutencao estimada para baixo toda vez que a tela abre.
    last_full_day = day - timedelta(days=1)
    diary = session.exec(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user.id)
        .where(DiaryEntry.entry_date >= start_day)
        .where(DiaryEntry.entry_date <= last_full_day)
    ).all()
    kcal_by_day: dict[date, float] = defaultdict(float)
    for entry in diary:
        kcal_by_day[entry.entry_date] += entry.kcal
    daily_intakes = list(kcal_by_day.values())

    estimate = estimate_maintenance(weigh_ins, daily_intakes, KCAL_PER_KG_FAT, bmr)

    formula_goals = compute_goals(profile, weight_kg)

    suggested_target: int | None = None
    if estimate.has_enough_data and estimate.estimated_maintenance_kcal is not None:
        suggested_target = target_calories_from_maintenance(
            profile, weight_kg, estimate.estimated_maintenance_kcal, bmr
        )
        # A estimativa impossivel manda na mensagem: nao adianta falar de ritmo de perda
        # quando o proprio numero denuncia que o diario nao foi preenchido inteiro.
        if estimate.is_below_bmr:
            message_code = "MEASURED_BELOW_BMR"
        else:
            message_code = _adaptive_message_code(
                profile, weight_kg, estimate.weekly_change_kg
            )
    else:
        message_code = "NOT_ENOUGH_DATA"

    return AdaptiveTdeeOut(
        has_enough_data=estimate.has_enough_data,
        span_days=estimate.span_days,
        weigh_ins=estimate.weigh_ins,
        days_logged=estimate.days_logged,
        days_discarded=estimate.days_discarded,
        min_span_days=MIN_SPAN_DAYS,
        min_weigh_ins=MIN_WEIGH_INS,
        min_days_logged=MIN_DAYS_LOGGED,
        avg_intake_kcal=estimate.avg_intake_kcal,
        weekly_change_kg=estimate.weekly_change_kg,
        estimated_maintenance_kcal=estimate.estimated_maintenance_kcal,
        bmr_kcal=round(bmr),
        formula_tdee_kcal=formula_goals.tdee_kcal,
        current_target_kcal=compute_goals(
            profile, weight_kg, maintenance_override=diet_maintenance_override(session, user.id)
        ).target_kcal,
        suggested_target_kcal=suggested_target,
        can_adopt=_can_adopt_estimate(message_code, suggested_target),
        message_code=message_code,
    )
