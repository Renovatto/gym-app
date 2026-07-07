import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ..config import settings
from ..deps import SessionDep
from ..models import PasswordResetToken, User
from ..schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
)
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..services.email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, session: SessionDep) -> TokenPair:
    email = data.email.lower()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="EMAIL_ALREADY_REGISTERED")
    user = User(email=email, password_hash=hash_password(data.password), locale=data.locale)
    session.add(user)
    session.commit()
    session.refresh(user)
    return _token_pair(user.id)


@router.post("/login", response_model=TokenPair)
def login(data: LoginRequest, session: SessionDep) -> TokenPair:
    user = session.exec(select(User).where(User.email == data.email.lower())).first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="INVALID_CREDENTIALS")
    return _token_pair(user.id)


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshRequest, session: SessionDep) -> TokenPair:
    user_id = decode_token(data.refresh_token, "refresh")
    if user_id is None or session.get(User, user_id) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN")
    return _token_pair(user_id)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(data: ForgotPasswordRequest, session: SessionDep) -> dict:
    """Gera um token de redefinicao e envia por e-mail (stub no dev). Responde sempre
    202, mesmo se o e-mail nao existir, para nao revelar quem tem conta."""
    user = session.exec(select(User).where(User.email == data.email.lower())).first()
    if user is not None:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.password_reset_minutes
        )
        session.add(
            PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
        )
        session.commit()
        send_password_reset_email(user.email, token)
    return {"status": "ok"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(data: ResetPasswordRequest, session: SessionDep) -> None:
    reset = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token == data.token)
    ).first()
    if reset is None or reset.used:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="INVALID_TOKEN")
    # datetime do SQLite volta sem fuso; tratamos como UTC para comparar.
    expires_at = reset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="TOKEN_EXPIRED")

    user = session.get(User, reset.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="INVALID_TOKEN")
    user.password_hash = hash_password(data.new_password)
    reset.used = True
    session.add(user)
    session.add(reset)
    session.commit()
