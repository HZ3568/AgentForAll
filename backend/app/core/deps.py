from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import decode_access_token
from backend.app.models.user import User
from backend.app.repositories.users import UserRepository


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise auth_error

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise auth_error from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise auth_error

    user = UserRepository(db).get_by_id(user_id)
    if user is None or user.status != "active":
        raise auth_error
    return user


def require_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
