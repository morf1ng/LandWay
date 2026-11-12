from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth import user_by_session, user_public
from app.store import store

_bearer = HTTPBearer(auto_error=False)
_AUTH_DISABLED = os.getenv("SCT_AUTH_DISABLED", "").lower() in ("1", "true", "yes")


def _demo_user() -> dict:
    data = store.read()
    user = data["users"][0] if data.get("users") else {
        "id": "demo",
        "username": "logist",
        "name": "Демо",
        "role": "Логист",
        "organization": "SCT",
    }
    return user_public(user)


def get_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Query(default=None, alias="access_token"),
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return access_token


def require_user(
    token: str | None = Depends(get_token),
) -> dict:
    if _AUTH_DISABLED:
        return _demo_user()
    user = user_by_session(store.read(), token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_public(user)
