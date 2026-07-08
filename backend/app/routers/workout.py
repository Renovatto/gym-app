from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, asc, desc, select

from ..deps import CurrentUser, SessionDep
from ..models import (
    Exercise,
    ExerciseLevel,
    MuscleGroup,
    Routine,
    RoutineExercise,
    SetLog,
    User,
    WorkoutSession,
)
from ..schemas import (
    ExerciseOut,
    RoutineIn,
    RoutineItemOut,
    RoutineOut,
    RoutinePeriodizationOut,
    SessionOut,
    SessionStartIn,
    SessionSummaryOut,
    SetLogIn,
    SetLogOut,
    WorkoutDayDetailOut,
    WorkoutDayExerciseOut,
)
from ..services.coaching import routines_periodization
from ..services.exercises import (
    TEMPLATES,
    exercise_by_slug,
    has_locale_translation,
    localized_name,
    to_exercise_out,
)
from ..services.text import normalize_search

router = APIRouter(tags=["workout"])


def _last_weight(session: Session, user_id: int, exercise_id: int) -> float | None:
    row = session.exec(
        select(SetLog.weight_kg)
        .join(WorkoutSession, SetLog.session_id == WorkoutSession.id)
        .where(WorkoutSession.user_id == user_id)
        .where(SetLog.exercise_id == exercise_id)
        .order_by(desc(SetLog.logged_at), desc(SetLog.id))
    ).first()
    return row


def _visible_exercise(session: Session, exercise_id: int, user_id: int) -> Exercise | None:
    ex = session.get(Exercise, exercise_id)
    if ex is None or (ex.user_id is not None and ex.user_id != user_id):
        return None
    return ex


# --- Catálogo -------------------------------------------------------------


@router.get("/exercises", response_model=list[ExerciseOut])
def list_exercises(
    user: CurrentUser,
    session: SessionDep,
    q: str = Query(default="", max_length=60),
    muscle_group: MuscleGroup | None = Query(default=None),
    level: ExerciseLevel | None = Query(default=None),
    full: bool = Query(default=False, description="true = base completa; false = só traduzidos"),
    limit: int = Query(default=100, ge=1, le=300),
) -> list[ExerciseOut]:
    query = select(Exercise).where(
        (Exercise.user_id.is_(None)) | (Exercise.user_id == user.id)
    )
    if muscle_group is not None:
        query = query.where(Exercise.muscle_group == muscle_group)
    if level is not None:
        query = query.where(Exercise.level == level)
    exercises = session.exec(query).all()

    term = normalize_search(q.strip())
    if term:
        # busca ignora acentos/caixa e vale para a base inteira (ignora `full`)
        exercises = [
            ex
            for ex in exercises
            if any(term in normalize_search(t.name) for t in ex.translations)
        ]
    elif not full:
        # Modo padrão mostra só exercícios com nome no idioma do usuário (curados);
        # modo completo mostra tudo (nomes em inglês como fallback).
        exercises = [ex for ex in exercises if has_locale_translation(ex, user.locale)]

    out = [to_exercise_out(session, ex, user.locale) for ex in exercises]
    out.sort(key=lambda e: e.name.lower())
    return out[:limit]


# --- Rotinas --------------------------------------------------------------


def _routine_out(session: Session, routine: Routine, user: User) -> RoutineOut:
    items = sorted(routine.items, key=lambda i: i.position)
    out_items = []
    for item in items:
        ex = session.get(Exercise, item.exercise_id)
        out_items.append(
            RoutineItemOut(
                id=item.id,
                exercise=to_exercise_out(session, ex, user.locale),
                position=item.position,
                target_sets=item.target_sets,
                target_reps=item.target_reps,
                target_weight_kg=item.target_weight_kg,
                target_duration_min=item.target_duration_min,
                rest_seconds=item.rest_seconds,
                last_weight_kg=_last_weight(session, user.id, item.exercise_id),
            )
        )
    return RoutineOut(id=routine.id, name=routine.name, position=routine.position, items=out_items)


@router.get("/me/routines", response_model=list[RoutineOut])
def list_routines(user: CurrentUser, session: SessionDep) -> list[RoutineOut]:
    routines = session.exec(
        select(Routine).where(Routine.user_id == user.id).order_by(asc(Routine.position), asc(Routine.id))
    ).all()
    return [_routine_out(session, r, user) for r in routines]


@router.get("/me/training/periodization", response_model=list[RoutinePeriodizationOut])
def training_periodization(
    user: CurrentUser,
    session: SessionDep,
    today: date = Query(..., description="Dia local do cliente (YYYY-MM-DD)"),
) -> list[RoutinePeriodizationOut]:
    """Ha quantas semanas cada rotina esta ativa e se ja passou da validade sugerida."""
    return routines_periodization(session, user, today)


@router.post("/me/routines", response_model=RoutineOut, status_code=status.HTTP_201_CREATED)
def create_routine(data: RoutineIn, user: CurrentUser, session: SessionDep) -> RoutineOut:
    count = len(session.exec(select(Routine.id).where(Routine.user_id == user.id)).all())
    routine = Routine(user_id=user.id, name=data.name, position=count)
    session.add(routine)
    session.flush()
    for position, item in enumerate(data.items):
        if _visible_exercise(session, item.exercise_id, user.id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="EXERCISE_NOT_FOUND")
        session.add(
            RoutineExercise(
                routine_id=routine.id,
                exercise_id=item.exercise_id,
                position=position,
                target_sets=item.target_sets,
                target_reps=item.target_reps,
                target_weight_kg=item.target_weight_kg,
                target_duration_min=item.target_duration_min,
                rest_seconds=item.rest_seconds,
            )
        )
    session.commit()
    session.refresh(routine)
    return _routine_out(session, routine, user)


def _get_owned_routine(session: Session, routine_id: int, user_id: int) -> Routine:
    routine = session.get(Routine, routine_id)
    if routine is None or routine.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ROUTINE_NOT_FOUND")
    return routine


@router.get("/me/routines/{routine_id}", response_model=RoutineOut)
def get_routine(routine_id: int, user: CurrentUser, session: SessionDep) -> RoutineOut:
    return _routine_out(session, _get_owned_routine(session, routine_id, user.id), user)


@router.put("/me/routines/{routine_id}", response_model=RoutineOut)
def update_routine(
    routine_id: int, data: RoutineIn, user: CurrentUser, session: SessionDep
) -> RoutineOut:
    routine = _get_owned_routine(session, routine_id, user.id)
    routine.name = data.name
    # limpar pela coleção (delete-orphan) evita re-adicionar instâncias deletadas
    routine.items.clear()
    session.flush()
    for position, item in enumerate(data.items):
        if _visible_exercise(session, item.exercise_id, user.id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="EXERCISE_NOT_FOUND")
        session.add(
            RoutineExercise(
                routine_id=routine.id,
                exercise_id=item.exercise_id,
                position=position,
                target_sets=item.target_sets,
                target_reps=item.target_reps,
                target_weight_kg=item.target_weight_kg,
                target_duration_min=item.target_duration_min,
                rest_seconds=item.rest_seconds,
            )
        )
    session.add(routine)
    session.commit()
    session.refresh(routine)
    return _routine_out(session, routine, user)


@router.delete("/me/routines/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(routine_id: int, user: CurrentUser, session: SessionDep) -> None:
    routine = _get_owned_routine(session, routine_id, user.id)
    # Preserva o histórico: sessões guardam routine_name, então só soltamos o vínculo.
    linked = session.exec(
        select(WorkoutSession).where(WorkoutSession.routine_id == routine_id)
    ).all()
    for ws in linked:
        ws.routine_id = None
        session.add(ws)
    session.delete(routine)
    session.commit()


@router.post("/me/routines/from-template", response_model=list[RoutineOut], status_code=status.HTTP_201_CREATED)
def create_from_template(
    user: CurrentUser,
    session: SessionDep,
    frequency: int = Query(..., ge=2, le=5),
) -> list[RoutineOut]:
    template = TEMPLATES.get(frequency)
    if template is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="TEMPLATE_NOT_FOUND")
    base = len(session.exec(select(Routine.id).where(Routine.user_id == user.id)).all())
    created: list[Routine] = []
    for offset, (name, slugs) in enumerate(template):
        routine = Routine(user_id=user.id, name=name, position=base + offset)
        session.add(routine)
        session.flush()
        for position, slug in enumerate(slugs):
            ex = exercise_by_slug(session, slug)
            if ex is None:
                continue
            session.add(
                RoutineExercise(routine_id=routine.id, exercise_id=ex.id, position=position)
            )
        created.append(routine)
    session.commit()
    for r in created:
        session.refresh(r)
    return [_routine_out(session, r, user) for r in created]


# --- Sessões (executar treino) -------------------------------------------


def _session_out(user_session: WorkoutSession) -> SessionOut:
    return SessionOut(
        id=user_session.id,
        routine_id=user_session.routine_id,
        routine_name=user_session.routine_name,
        started_at=user_session.started_at,
        finished_at=user_session.finished_at,
        sets=[SetLogOut.model_validate(s) for s in user_session.sets],
    )


@router.post("/me/routines/{routine_id}/complete", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def complete_routine(routine_id: int, user: CurrentUser, session: SessionDep) -> SessionOut:
    """Registra o treino como feito conforme planejado, sem passar pela execução
    passo a passo. Cria uma sessão já finalizada com as séries-alvo marcadas."""
    routine = _get_owned_routine(session, routine_id, user.id)
    now = datetime.now(timezone.utc)
    ws = WorkoutSession(
        user_id=user.id, routine_id=routine.id, routine_name=routine.name,
        started_at=now, finished_at=now,
    )
    session.add(ws)
    session.flush()
    for item in sorted(routine.items, key=lambda i: i.position):
        weight = _last_weight(session, user.id, item.exercise_id) or item.target_weight_kg or 0
        for set_number in range(1, item.target_sets + 1):
            session.add(
                SetLog(
                    session_id=ws.id,
                    exercise_id=item.exercise_id,
                    set_number=set_number,
                    reps=item.target_reps,
                    weight_kg=weight,
                    duration_min=item.target_duration_min,
                    done=True,
                )
            )
    session.commit()
    session.refresh(ws)
    return _session_out(ws)


def _find_active_session(session: Session, user_id: int) -> WorkoutSession | None:
    return session.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user_id)
        .where(WorkoutSession.finished_at.is_(None))
        .order_by(desc(WorkoutSession.started_at))
    ).first()


@router.get("/me/sessions/active", response_model=SessionOut | None)
def active_session(user: CurrentUser, session: SessionDep) -> SessionOut | None:
    ws = _find_active_session(session, user.id)
    return _session_out(ws) if ws else None


def _workout_day_detail(session: Session, ws: WorkoutSession, locale: str) -> WorkoutDayDetailOut:
    """Monta a visualizacao (somente leitura) de um treino concluido: series
    agrupadas por exercicio, na ordem em que aparecem, com nome traduzido."""
    order: list[int] = []
    sets_by_exercise: dict[int, list[SetLog]] = {}
    for s in sorted(ws.sets, key=lambda x: (x.exercise_id, x.set_number)):
        if s.exercise_id not in sets_by_exercise:
            sets_by_exercise[s.exercise_id] = []
            order.append(s.exercise_id)
        sets_by_exercise[s.exercise_id].append(s)

    exercises: list[WorkoutDayExerciseOut] = []
    total_volume = 0.0
    total_sets = 0
    for exercise_id in order:
        exercise = session.get(Exercise, exercise_id)
        name = localized_name(session, exercise, locale) if exercise else str(exercise_id)
        is_cardio = bool(exercise and exercise.kind.value == "cardio")
        exercise_sets = sets_by_exercise[exercise_id]
        exercises.append(
            WorkoutDayExerciseOut(
                exercise_name=name,
                is_cardio=is_cardio,
                sets=[SetLogOut.model_validate(s) for s in exercise_sets],
            )
        )
        for s in exercise_sets:
            if s.done:
                total_volume += s.reps * s.weight_kg
                total_sets += 1

    return WorkoutDayDetailOut(
        session_id=ws.id,
        routine_name=ws.routine_name,
        started_at=ws.started_at,
        finished_at=ws.finished_at,
        total_volume_kg=round(total_volume, 1),
        total_sets=total_sets,
        exercises=exercises,
    )


@router.get("/me/sessions/by-day", response_model=list[WorkoutDayDetailOut])
def sessions_by_day(
    user: CurrentUser,
    session: SessionDep,
    day: date = Query(..., description="Dia local do cliente (YYYY-MM-DD)"),
    tz_offset: int = Query(0, description="Date.getTimezoneOffset() do cliente"),
) -> list[WorkoutDayDetailOut]:
    """Treinos concluidos em um dia local (para a visualizacao do calendario)."""
    local_midnight = datetime.combine(day, time.min)
    start = (local_midnight + timedelta(minutes=tz_offset)).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    sessions = session.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .where(WorkoutSession.finished_at.is_not(None))
        .where(WorkoutSession.started_at >= start)
        .where(WorkoutSession.started_at < end)
        .order_by(asc(WorkoutSession.started_at))
    ).all()
    return [_workout_day_detail(session, ws, user.locale) for ws in sessions]


@router.post("/me/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(data: SessionStartIn, user: CurrentUser, session: SessionDep) -> SessionOut:
    # evita sessões duplicadas: reaproveita a ativa com séries, descarta a vazia
    active = _find_active_session(session, user.id)
    if active is not None:
        if active.sets:
            return _session_out(active)
        session.delete(active)
        session.flush()

    routine_name = None
    if data.routine_id is not None:
        routine = _get_owned_routine(session, data.routine_id, user.id)
        routine_name = routine.name
    ws = WorkoutSession(user_id=user.id, routine_id=data.routine_id, routine_name=routine_name)
    session.add(ws)
    session.commit()
    session.refresh(ws)
    return _session_out(ws)


def _get_owned_session(session: Session, session_id: int, user_id: int) -> WorkoutSession:
    ws = session.get(WorkoutSession, session_id)
    if ws is None or ws.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SESSION_NOT_FOUND")
    return ws


@router.post("/me/sessions/{session_id}/sets", response_model=SetLogOut, status_code=status.HTTP_201_CREATED)
def log_set(
    session_id: int, data: SetLogIn, user: CurrentUser, session: SessionDep
) -> SetLog:
    ws = _get_owned_session(session, session_id, user.id)
    if ws.finished_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="SESSION_FINISHED")
    if _visible_exercise(session, data.exercise_id, user.id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="EXERCISE_NOT_FOUND")
    log = SetLog(
        session_id=ws.id,
        exercise_id=data.exercise_id,
        set_number=data.set_number,
        reps=data.reps,
        weight_kg=data.weight_kg,
        duration_min=data.duration_min,
        done=data.done,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


@router.delete("/me/sessions/{session_id}/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_set(
    session_id: int, set_id: int, user: CurrentUser, session: SessionDep
) -> None:
    _get_owned_session(session, session_id, user.id)
    log = session.get(SetLog, set_id)
    if log is None or log.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SET_NOT_FOUND")
    session.delete(log)
    session.commit()


@router.post("/me/sessions/{session_id}/finish", response_model=SessionOut)
def finish_session(session_id: int, user: CurrentUser, session: SessionDep) -> SessionOut:
    ws = _get_owned_session(session, session_id, user.id)
    if ws.finished_at is None:
        ws.finished_at = datetime.now(timezone.utc)
        session.add(ws)
        session.commit()
        session.refresh(ws)
    return _session_out(ws)


@router.get("/me/sessions", response_model=list[SessionSummaryOut])
def list_sessions(user: CurrentUser, session: SessionDep) -> list[SessionSummaryOut]:
    sessions = session.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .order_by(desc(WorkoutSession.started_at))
    ).all()
    summaries = []
    for ws in sessions:
        volume = sum(s.reps * s.weight_kg for s in ws.sets if s.done)
        summaries.append(
            SessionSummaryOut(
                id=ws.id,
                routine_name=ws.routine_name,
                started_at=ws.started_at,
                finished_at=ws.finished_at,
                total_sets=len([s for s in ws.sets if s.done]),
                total_volume_kg=round(volume, 1),
            )
        )
    return summaries


@router.get("/me/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: int, user: CurrentUser, session: SessionDep) -> SessionOut:
    return _session_out(_get_owned_session(session, session_id, user.id))


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_session(session_id: int, user: CurrentUser, session: SessionDep) -> None:
    ws = _get_owned_session(session, session_id, user.id)
    session.delete(ws)
    session.commit()
