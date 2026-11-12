from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_token, require_user
from app.services.auth import login as do_login
from app.services.auth import logout as do_logout
from app.services.auth import user_public
from app.store import store

router = APIRouter()


@router.post("/login")
def login(payload: dict):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="Укажите логин и пароль")
    holder: dict = {}

    def mutate(data):
        try:
            session, user = do_login(data, username, password)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        holder["session"] = session
        holder["user"] = user

    try:
        store.update(mutate)
    except HTTPException:
        raise
    session = holder["session"]
    user = holder["user"]
    return {
        "token": session["token"],
        "expiresAt": session["expiresAt"],
        "user": user_public(user),
    }


@router.post("/logout")
def logout(token: str | None = Depends(get_token)):
    if not token:
        return {"ok": True}

    def mutate(data):
        do_logout(data, token)

    store.update(mutate)
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(require_user)):
    return {"user": user}
