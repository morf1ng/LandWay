"""Демонстрационная авторизация прототипа (не production).

Пароли хранятся как SHA-256, сессии — в общем JSON-хранилище.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from app.services.risk import iso

SESSION_TTL_HOURS = 24 * 7


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def default_users() -> list[dict]:
    return [
        {
            "id": "user-logist",
            "username": "logist",
            "passwordHash": hash_password("demo123"),
            "name": "Демо-логист",
            "role": "Логист коридора Север — Юг",
            "organization": "Smart Caspian Transit",
        },
        {
            "id": "user-admin",
            "username": "admin",
            "passwordHash": hash_password("admin123"),
            "name": "Администратор",
            "role": "Администратор платформы",
            "organization": "Smart Caspian Transit",
        },
    ]


def ensure_auth_fields(data: dict) -> None:
    if "users" not in data or not data["users"]:
        data["users"] = default_users()
    if "sessions" not in data:
        data["sessions"] = []
    if "profile" not in data:
        data["profile"] = {
            "name": data["users"][0]["name"],
            "role": data["users"][0]["role"],
            "organization": data["users"][0]["organization"],
        }


def prune_sessions(data: dict, moment: datetime | None = None) -> None:
    now = moment or datetime.now().replace(microsecond=0)
    alive = []
    for session in data.get("sessions", []):
        expires = datetime.fromisoformat(session["expiresAt"])
        if expires > now:
            alive.append(session)
    data["sessions"] = alive


def find_user(data: dict, username: str) -> dict | None:
    needle = username.strip().lower()
    for user in data.get("users", []):
        if user["username"].lower() == needle:
            return user
    return None


def user_public(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "organization": user["organization"],
    }


def verify_password(user: dict, password: str) -> bool:
    return user.get("passwordHash") == hash_password(password)


def create_session(data: dict, user: dict, moment: datetime | None = None) -> dict:
    now = moment or datetime.now().replace(microsecond=0)
    prune_sessions(data, now)
    token = secrets.token_urlsafe(32)
    expires = now + timedelta(hours=SESSION_TTL_HOURS)
    session = {
        "token": token,
        "userId": user["id"],
        "createdAt": iso(now),
        "expiresAt": iso(expires),
    }
    data.setdefault("sessions", []).append(session)
    # Профиль в UI совпадает с вошедшим пользователем.
    data["profile"] = {
        "name": user["name"],
        "role": user["role"],
        "organization": user["organization"],
        "userId": user["id"],
    }
    return session


def login(data: dict, username: str, password: str) -> tuple[dict, dict]:
    user = find_user(data, username)
    if user is None or not verify_password(user, password):
        raise ValueError("Неверный логин или пароль")
    session = create_session(data, user)
    _journal_login(data, user, session)
    return session, user


def logout(data: dict, token: str) -> bool:
    before = len(data.get("sessions", []))
    data["sessions"] = [item for item in data.get("sessions", []) if item.get("token") != token]
    return len(data["sessions"]) < before


def session_by_token(data: dict, token: str | None) -> dict | None:
    if not token:
        return None
    now = datetime.now().replace(microsecond=0)
    for session in data.get("sessions", []):
        if session.get("token") != token:
            continue
        expires = datetime.fromisoformat(session["expiresAt"])
        if expires <= now:
            continue
        return session
    return None


def user_by_session(data: dict, token: str | None) -> dict | None:
    session = session_by_token(data, token)
    if session is None:
        return None
    user_id = session["userId"]
    for user in data.get("users", []):
        if user["id"] == user_id:
            return user
    return None


def _journal_login(data: dict, user: dict, session: dict) -> None:
    data.setdefault("journal", []).insert(
        0,
        {
            "id": f"j-{uuid.uuid4().hex[:10]}",
            "shipmentId": None,
            "type": "auth",
            "title": "Вход в систему",
            "result": "успешно",
            "details": f"Пользователь {user['username']} ({user['name']}). Сессия до {session['expiresAt']}.",
            "at": session["createdAt"],
        },
    )


def update_user_profile(data: dict, user_id: str, payload: dict) -> dict:
    user = next((item for item in data["users"] if item["id"] == user_id), None)
    if user is None:
        raise ValueError("Пользователь не найден")
    for key in ("name", "role", "organization"):
        if payload.get(key):
            user[key] = str(payload[key]).strip()
    data["profile"] = {
        "name": user["name"],
        "role": user["role"],
        "organization": user["organization"],
        "userId": user["id"],
    }
    return data["profile"]
