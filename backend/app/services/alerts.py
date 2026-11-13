"""Сбор предупреждений из уже посчитанного прогноза."""

from __future__ import annotations

from datetime import datetime

from app.services.risk import iso, parse_dt


def _ru_datetime(value: str | None) -> str:
    moment = parse_dt(value)
    return moment.strftime("%d.%m.%Y, %H:%M") if moment else "—"


def sync_notifications(data: dict, now: datetime) -> None:
    previous = {item["id"]: item for item in data.get("notifications", [])}
    notifications = []
    predictions = {item["shipmentId"]: item for item in data["predictions"]}
    rules = [
        ("train_delay", "Риск задержки поезда", "поезд"),
        ("port_workload", "Высокая загруженность порта", "высокая загруженность порта"),
        ("weather", "Неблагоприятная погода", "неблагоприятная погода"),
        ("wind", "Неблагоприятная погода", "сильный ветер"),
        ("missed_sailing", "Риск пропуска морского рейса", "пропустить морской рейс"),
        ("documents", "Проблемы с документами", "документ"),
    ]
    for shipment in data["shipments"]:
        prediction = predictions.get(shipment["id"])
        if not prediction or prediction["riskLevel"] == "none":
            continue
        text = " ".join(prediction["reasons"])
        seen_titles = set()
        for type_id, title, needle in rules:
            if needle not in text:
                continue
            if title in seen_titles and type_id == "wind":
                continue
            seen_titles.add(title)
            note_id = f"{shipment['id']}:{type_id}"
            old = previous.get(note_id)
            href = f"/customs?shipment={shipment['id']}" if type_id == "documents" else f"/shipments/{shipment['id']}"
            matching = [reason for reason in prediction["reasons"] if needle in reason or (type_id == "weather" and "ветер" in reason)]
            description = f"{shipment['id']}. " + ("; ".join(matching) if matching else text)
            if type_id in ("train_delay", "missed_sailing"):
                delay = prediction.get("estimatedDelay")
                delay_text = f"{int(round(float(delay)))} ч" if delay is not None else "не определена"
                description += (
                    f". Прогноз прибытия {_ru_datetime(shipment.get('predictedArrival'))} МСК, "
                    f"задержка к плану {delay_text}"
                )
            changed = old is not None and old.get("description") != description
            notifications.append(
                {
                    "id": note_id,
                    "shipmentId": shipment["id"],
                    "type": type_id,
                    "title": title,
                    "description": description,
                    "severity": prediction["riskLevel"] if prediction["riskLevel"] in ("low", "medium", "high") else "low",
                    "createdAt": iso(now) if not old or changed else old["createdAt"],
                    "read": bool(old and old["read"] and not changed),
                    "href": href,
                }
            )
    data["notifications"] = notifications
