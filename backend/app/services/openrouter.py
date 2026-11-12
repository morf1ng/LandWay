"""On-demand explanation of a calculated shipment forecast via OpenRouter."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL = "nvidia/nemotron-3.5-lightning:free"
KEY_FILE = Path(__file__).resolve().parents[2] / ".secrets" / "openrouter.key"


class AIUnavailable(Exception):
    pass


def _key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key:
        raise AIUnavailable("Ключ OpenRouter не настроен на сервере")
    return key


def explain(row: dict) -> dict:
    facts = {
        "груз": row["id"],
        "маршрут": row["route"],
        "вероятность_задержки_процентов": row["probability"],
        "уровень_риска": row["riskLevel"],
        "оценка_задержки_часов": row["estimatedDelay"],
        "прогноз_прибытия": row["predictedArrival"],
        "факторы": row["reasons"],
        "рекомендация_правил": row["recommendation"],
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": (
                "Ты помощник логиста. Ответь на русском языке кратко и предметно. "
                "Используй только факты из JSON пользователя. Не меняй проценты, сроки и часы; "
                "не утверждай, что перевозчик или таможня что-либо подтвердили. "
                "Не выдумывай оперативные данные, бронирование, GPS или доступность маршрутов. "
                "Сформулируй 2–3 предложения: почему риск возник и какое действие логисту стоит проверить. "
                "Это демонстрационные данные. Не включай внутренние рассуждения."
            )},
            {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "reasoning": {"enabled": False},
        "max_tokens": 1000,
        "stream": False,
    }
    request = Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=75) as response:
            result = json.load(response)
    except HTTPError as exc:
        if exc.code == 429:
            raise AIUnavailable("Бесплатная модель временно ограничила число запросов. Повторите позже") from exc
        raise AIUnavailable(f"OpenRouter вернул ошибку {exc.code}") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise AIUnavailable("Сервис ИИ сейчас недоступен") from exc

    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise AIUnavailable("Модель не вернула текстовый ответ")
    return {
        "shipmentId": row["id"],
        "model": MODEL,
        "analysis": content.strip()[:3000],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "demo_forecast",
    }
