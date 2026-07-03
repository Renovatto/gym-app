from fastapi import APIRouter, HTTPException, status
from sqlmodel import desc, select

from ..deps import CurrentUser, SessionDep
from ..models import Profile, WeightLog, WeightSource
from ..schemas import GoalsOut, LocaleUpdate, ProfileIn, ProfileOut, UserOut
from ..services.goals import compute_goals

router = APIRouter(prefix="/me", tags=["me"])


def _latest_weight(session: SessionDep, user_id: int) -> WeightLog | None:
    return session.exec(
        select(WeightLog)
        .where(WeightLog.user_id == user_id)
        .order_by(desc(WeightLog.logged_at), desc(WeightLog.id))
    ).first()


def _get_profile(session: SessionDep, user_id: int) -> Profile:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="PROFILE_NOT_FOUND")
    return profile


@router.get("", response_model=UserOut)
def get_me(user: CurrentUser, session: SessionDep) -> UserOut:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    return UserOut(
        id=user.id,
        email=user.email,
        locale=user.locale,
        plan=user.plan,
        has_profile=profile is not None,
    )


@router.put("/locale", response_model=UserOut)
def update_locale(data: LocaleUpdate, user: CurrentUser, session: SessionDep) -> UserOut:
    user.locale = data.locale
    session.add(user)
    session.commit()
    return get_me(user, session)


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: CurrentUser, session: SessionDep) -> ProfileOut:
    profile = _get_profile(session, user.id)
    latest = _latest_weight(session, user.id)
    return ProfileOut(
        height_cm=profile.height_cm,
        weight_kg=latest.weight_kg if latest else None,
        birthdate=profile.birthdate,
        sex=profile.sex,
        activity_level=profile.activity_level,
        objective=profile.objective,
        diet_enabled=profile.diet_enabled,
        scale_mac=profile.scale_mac,
    )


@router.put("/profile", response_model=ProfileOut)
def upsert_profile(data: ProfileIn, user: CurrentUser, session: SessionDep) -> ProfileOut:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        profile = Profile(user_id=user.id, **data.model_dump(exclude={"weight_kg"}))
    else:
        for field, value in data.model_dump(exclude={"weight_kg"}).items():
            setattr(profile, field, value)
    session.add(profile)

    latest = _latest_weight(session, user.id)
    if latest is None or latest.weight_kg != data.weight_kg:
        session.add(
            WeightLog(user_id=user.id, weight_kg=data.weight_kg, source=WeightSource.manual)
        )
    session.commit()
    return get_profile(user, session)


@router.get("/goals", response_model=GoalsOut)
def get_goals(user: CurrentUser, session: SessionDep) -> GoalsOut:
    profile = _get_profile(session, user.id)
    latest = _latest_weight(session, user.id)
    if latest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="WEIGHT_NOT_FOUND")
    return compute_goals(profile, latest.weight_kg)
