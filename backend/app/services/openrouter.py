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


def _parse_action_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    plans = data.get("actionPlans")
    if not isinstance(plans, list):
        return None
    out: list[dict] = []
    for item in plans:
        if not isinstance(item, dict):
            continue
        problem = str(item.get("problem") or "").strip()
        solutions = item.get("solutions")
        if not problem or not isinstance(solutions, list):
            continue
        clean = [str(s).strip() for s in solutions if str(s).strip()][:3]
        if len(clean) < 3:
            continue
        out.append({"problem": problem, "solutions": clean})
    if not out:
        return None
    summary = str(data.get("summary") or "").strip()
    return {"actionPlans": out, "summary": summary[:800]}


def explain(row: dict) -> dict:
    from app.services.action_playbook import build_action_plans

    playbook = build_action_plans(row)
    facts = {
        "груз": row["id"],
        "маршрут": row["route"],
        "вероятность_задержки_процентов": row["probability"],
        "уровень_риска": row["riskLevel"],
        "оценка_задержки_часов": row["estimatedDelay"],
        "прогноз_прибытия": row["predictedArrival"],
        "факторы": row["reasons"],
        "рекомендация_правил": row["recommendation"],
        "черновик_шагов": playbook,
        "история_коридора": {
            "режим": row.get("historyMode"),
            "источник_данных": row.get("historySource"),
            "похожих_рейсов": row.get("historyMatchCount"),
            "коридор": row.get("historyCorridor"),
            "примечание": row.get("historyNote"),
            "признаки_на_момент_прогноза": row.get("historyFeatures"),
            "критерии_похожести": row.get("historyFactors"),
            "доля_пропуска_парома_среди_похожих": row.get("historyMissRate"),
            "медиана_задержки_похожих_часов": row.get("historyMedianDelayHours"),
        },
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": (
                "Ты помощник логиста Smart Caspian Transit. Ответь на русском только валидным JSON без markdown. "
                "Схема: {\"summary\": \"одно-два предложения без изменения цифр\", "
                "\"actionPlans\": [{\"problem\": \"краткое имя проблемы\", "
                "\"solutions\": [\"шаг1\", \"шаг2\", \"шаг3\"]}]}. "
                "Для КАЖДОЙ записи из facts.факторы (или объединённой смысловой проблемы) дай ровно 3 готовых "
                "условных решения в форме «Если … — …». Используй только facts и черновик_шагов; не выдумывай "
                "бронирования, GPS, подтверждения перевозчика. Не меняй проценты, часы, даты. Демонстрационный контур."
            )},
            {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "reasoning": {"enabled": False},
        "max_tokens": 2200,
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

    parsed = _parse_action_json(content)
    if parsed:
        analysis = parsed["summary"] or "Готовые шаги по каждому фактору риска ниже."
        action_plans = parsed["actionPlans"]
        source = "demo_forecast_ai"
    else:
        analysis = content.strip()[:800]
        action_plans = playbook
        source = "demo_forecast_playbook"

    return {
        "shipmentId": row["id"],
        "model": MODEL,
        "analysis": analysis,
        "actionPlans": action_plans,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }
