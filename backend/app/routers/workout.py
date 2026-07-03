from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, asc, desc, select

from ..deps import CurrentUser, SessionDep
from ..models import (
    Exercise,
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
    SessionOut,
    SessionStartIn,
    SessionSummaryOut,
    SetLogIn,
    SetLogOut,
)
from ..services.exercises import TEMPLATES, exercise_by_slug, to_exercise_out

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
    muscle_group: MuscleGroup | None = Query(default=None),
) -> list[ExerciseOut]:
    query = select(Exercise).where(
        (Exercise.user_id.is_(None)) | (Exercise.user_id == user.id)
    )
    if muscle_group is not None:
        query = query.where(Exercise.muscle_group == muscle_group)
    exercises = session.exec(query).all()
    out = [to_exercise_out(session, ex, user.locale) for ex in exercises]
    out.sort(key=lambda e: e.name.lower())
    return out


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
    for item in list(routine.items):
        session.delete(item)
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


@router.post("/me/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(data: SessionStartIn, user: CurrentUser, session: SessionDep) -> SessionOut:
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
