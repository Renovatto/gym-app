from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ..deps import SessionDep
from ..models import User
from ..schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

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
