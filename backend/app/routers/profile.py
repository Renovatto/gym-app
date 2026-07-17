from fastapi import APIRouter, HTTPException, status
from sqlmodel import desc, select

from ..deps import CurrentUser, SessionDep, user_is_admin
from ..models import Profile, User, WeightLog, WeightSource
from ..schemas import (
    EmailChange,
    GoalsOut,
    LocaleUpdate,
    PasswordChange,
    ProfileIn,
    ProfileOut,
    UserOut,
)
from ..security import hash_password, verify_password
from ..services.dietplan import maintenance_override as diet_maintenance_override
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
        is_admin=user_is_admin(user),
    )


@router.put("/locale", response_model=UserOut)
def update_locale(data: LocaleUpdate, user: CurrentUser, session: SessionDep) -> UserOut:
    user.locale = data.locale
    session.add(user)
    session.commit()
    return get_me(user, session)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: PasswordChange, user: CurrentUser, session: SessionDep) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="WRONG_PASSWORD")
    user.password_hash = hash_password(data.new_password)
    session.add(user)
    session.commit()


@router.put("/email", response_model=UserOut)
def change_email(data: EmailChange, user: CurrentUser, session: SessionDep) -> UserOut:
    # A troca de e-mail nao pede senha (o usuario ja esta autenticado por JWT). Se uma
    # senha for enviada, ela e verificada; caso contrario, seguimos direto.
    if data.current_password and not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="WRONG_PASSWORD")
    new_email = data.new_email.lower()
    if new_email != user.email:
        taken = session.exec(select(User).where(User.email == new_email)).first()
        if taken is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="EMAIL_ALREADY_REGISTERED")
        user.email = new_email
        session.add(user)
        session.commit()
    return get_me(user, session)


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: CurrentUser, session: SessionDep) -> ProfileOut:
    profile = _get_profile(session, user.id)
    latest = _latest_weight(session, user.id)
    return ProfileOut(
        first_name=profile.first_name,
        last_name=profile.last_name,
        height_cm=profile.height_cm,
        weight_kg=latest.weight_kg if latest else None,
        birthdate=profile.birthdate,
        sex=profile.sex,
        activity_level=profile.activity_level,
        objective=profile.objective,
        cut_intensity=profile.cut_intensity,
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
    return compute_goals(
        profile, latest.weight_kg, maintenance_override=diet_maintenance_override(session, user.id)
    )
