from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from .config import settings
from .db import get_session
from .models import User
from .security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="NOT_AUTHENTICATED")
    user_id = decode_token(credentials.credentials, "access")
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="USER_NOT_FOUND")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def user_is_admin(user: User) -> bool:
    """Admin = e-mail na allowlist (settings.admin_emails), sem coluna no banco."""
    return user.email.lower() in {e.lower() for e in settings.admin_emails}


def require_admin(user: CurrentUser) -> User:
    if not user_is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="ADMIN_ONLY")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
