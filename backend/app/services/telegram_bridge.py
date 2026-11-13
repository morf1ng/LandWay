"""Отправка уведомлений в отдельный Telegram-бот. Токен бота хранится только на Vercel."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

SECRET_FILE = Path(__file__).resolve().parents[2] / ".secrets" / "telegram.env"


def bridge_config() -> dict[str, str]:
    url = os.getenv("TELEGRAM_BOT_URL", "").strip().rstrip("/")
    secret = os.getenv("TELEGRAM_NOTIFY_SECRET", "").strip()
    if SECRET_FILE.exists():
        for line in SECRET_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if key == "TELEGRAM_BOT_URL" and not url:
                url = value.rstrip("/")
            elif key == "TELEGRAM_NOTIFY_SECRET" and not secret:
                secret = value
    return {"url": url, "secret": secret}


def _request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    cfg = bridge_config()
    if not cfg["url"] or not cfg["secret"]:
        return {"ok": False, "reason": "unconfigured"}
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{cfg['url']}{path}",
        data=body,
        headers={"Content-Type": "application/json", "x-landway-secret": cfg["secret"]},
        method=method,
    )
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read().decode("utf-8")
    except (URLError, TimeoutError, ValueError):
        return {"ok": False, "reason": "failed"}
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"ok": False, "reason": "failed"}
    return data if isinstance(data, dict) else {"ok": False, "reason": "failed"}


def remember_chats(data: dict) -> list[str]:
    known = [str(item) for item in data.get("telegramChats") or []]
    remote = _request("/api/chats")
    incoming = [str(item) for item in remote.get("chats") or []]
    merged = list(dict.fromkeys([*known, *incoming]))
    data["telegramChats"] = merged
    return merged


def bot_profile() -> dict:
    info = _request("/api/info")
    if not info.get("username"):
        return {"configured": bool(bridge_config()["url"]), "username": None, "link": None}
    username = str(info["username"]).lstrip("@")
    return {"configured": True, "username": username, "link": f"https://t.me/{username}"}


def push_notice(data: dict, text: str) -> str:
    chats = remember_chats(data)
    cfg = bridge_config()
    if not cfg["url"]:
        return "unconfigured"
    if not chats:
        return "no_subscribers"
    result = _request("/api/notify", "POST", {"text": text, "chats": chats})
    if result.get("ok"):
        return "sent"
    return "failed"
