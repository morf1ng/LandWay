"""Сборка маршрутов из шаблонов и сравнение альтернатив."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.catalog import CITIES, PORT_NAMES, PORTS, ROUTE_TEMPLATES, place, sea_distance, template_by_id
from app.services.carbon import calculate
import copy

from app.services.risk import assess, iso, parse_dt, stage_arrival
from app.services.port_restrictions import block_apply_reason, route_restriction_summary
from app.services.stage_schedule import stamp_schedule_on_create, sync_stage_chain


def known_place(name: str) -> bool:
    if any(port["name"] == name for port in PORTS):
        return True
    return name in CITIES


def template_is_valid(template: dict) -> bool:
    stages = template.get("stages") or []
    if len(stages) < 2:
        return False
    for stage in stages:
        if stage["transport"] not in ("rail", "sea", "road"):
            return False
        if not known_place(stage["from"]) or not known_place(stage["to"]):
            return False
    return True


def materialize(template: dict, departure: datetime, route_id: str, shipment_id: str) -> dict:
    if not template_is_valid(template):
        raise ValueError("У альтернативы нет необходимых точек и этапов")
    cursor = departure
    stages = []
    for index, spec in enumerate(template["stages"], start=1):
        start = cursor
        if spec["transport"] == "sea":
            buffer_hours = float(spec.get("bufferHours") or 10)
            ship_at = start + timedelta(hours=buffer_hours)
            end = ship_at + timedelta(hours=float(spec["hours"]))
            ship_departure = iso(ship_at)
        else:
            end = start + timedelta(hours=float(spec["hours"]))
            ship_departure = None
        stages.append(
            stamp_schedule_on_create(
                {
                    "id": f"{route_id}-{index}",
                    "routeId": route_id,
                    "location": spec["from"],
                    "nextLocation": spec["to"],
                    "transportType": spec["transport"],
                    "plannedStart": iso(start),
                    "plannedArrival": iso(end),
                    "actualArrival": None,
                    "status": "pending",
                    "distanceKm": spec["distanceKm"],
                    "delayHours": 0,
                    "shipDeparture": ship_departure,
                    "description": spec["description"],
                }
            )
        )
        cursor = end
    distance = sum(stage["distanceKm"] for stage in stages)
    duration = round((cursor - departure).total_seconds() / 3600, 1)
    return {
        "id": route_id,
        "shipmentId": shipment_id,
        "name": template["name"],
        "templateId": template["id"],
        "origin": template["origin"],
        "destination": template["destination"],
        "stages": stages,
        "distance": distance,
        "estimatedDuration": duration,
        "estimatedCost": template["cost"],
        "carbonFootprint": 0,
    }


def generic_template(origin: str, destination: str, sequence: list[str]) -> dict:
    sail = sea_distance(origin, destination)
    sea = {
        "from": origin,
        "to": destination,
        "transport": "sea",
        "distanceKm": sail,
        "hours": 50,
        "bufferHours": 10,
        "description": f"Морской участок {origin} — {destination}",
    }
    if sequence == ["rail", "road", "sea"]:
        stages = [
            {
                "from": "Саратов",
                "to": "Волгоград",
                "transport": "rail",
                "distanceKm": 380,
                "hours": 14,
                "bufferHours": 0,
                "description": "Железнодорожный участок",
            },
            {
                "from": "Волгоград",
                "to": origin,
                "transport": "road",
                "distanceKm": 400,
                "hours": 12,
                "bufferHours": 0,
                "description": "Автомобильный подвоз к порту",
            },
            sea,
        ]
    elif sequence and sequence[0] == "rail":
        start = "Саратов" if origin == "Астрахань" else "Волгоград"
        if start == origin:
            start = "Саратов"
        stages = [
            {
                "from": start,
                "to": origin,
                "transport": "rail",
                "distanceKm": 450,
                "hours": 18,
                "bufferHours": 0,
                "description": "Железнодорожный подвод к порту",
            },
            sea,
        ]
    else:
        start = "Каспийск" if origin == "Махачкала" else "Волгоград"
        if start == origin:
            start = "Саратов"
        stages = [
            {
                "from": start,
                "to": origin,
                "transport": "road",
                "distanceKm": 180,
                "hours": 6,
                "bufferHours": 0,
                "description": "Автомобильный подвоз к порту",
            },
            sea,
        ]
    distance = sum(item["distanceKm"] for item in stages)
    return {
        "id": "generic-" + "-".join(sequence),
        "name": "Сформированный маршрут " + " + ".join(sequence),
        "origin": origin,
        "destination": destination,
        "sequence": sequence,
        "cost": int(15000 + distance * 40),
        "stages": stages,
    }


def resolve_template(origin: str, destination: str, sequence: list[str]) -> dict:
    from app.catalog import match_template

    found = match_template(origin, destination, sequence)
    if found and template_is_valid(found):
        return found
    template = generic_template(origin, destination, sequence)
    if not template_is_valid(template):
        raise ValueError("Не удалось собрать маршрут с нужными точками")
    return template


def route_duration_hours(route: dict) -> float:
    stages = route.get("stages") or []
    if not stages:
        return 0
    start = parse_dt(stages[0].get("schedulePlannedStart") or stages[0]["plannedStart"])
    end = stage_arrival(stages[-1]) or parse_dt(stages[-1]["plannedArrival"])
    if not start or not end:
        return float(route.get("estimatedDuration") or 0)
    return round((end - start).total_seconds() / 3600, 1)


TRANSFER_BUFFER_HOURS = 2.0


def switch_context(shipment: dict, route: dict, now: datetime) -> dict:
    """Узел переключения и этапы, которые уже нельзя отменить."""
    stages = route.get("stages") or []
    if not stages:
        raise ValueError("У груза нет этапов маршрута")

    completed = [stage for stage in stages if stage.get("status") == "completed"]
    active = next((stage for stage in stages if stage.get("status") in ("in_progress", "delayed")), None)
    pending = [stage for stage in stages if stage.get("status") == "pending"]

    if active:
        eta = stage_arrival(active) or now
        return {
            "node": active["nextLocation"],
            "eta": eta,
            "keptStages": completed + [active],
            "mode": "active_leg",
            "note": f"Активный участок {active['location']} → {active['nextLocation']} сохранён",
        }

    if shipment.get("currentPort") and completed:
        eta = stage_arrival(completed[-1]) or now
        return {
            "node": shipment["currentPort"],
            "eta": eta,
            "keptStages": copy.deepcopy(completed),
            "mode": "at_port",
            "note": f"Груз в порту {shipment['currentPort']}",
        }

    if completed and pending:
        eta = stage_arrival(completed[-1]) or parse_dt(pending[0]["plannedStart"]) or now
        return {
            "node": pending[0]["location"],
            "eta": eta,
            "keptStages": copy.deepcopy(completed),
            "mode": "after_leg",
            "note": "Пройденные этапы сохранены",
        }

    departure = parse_dt(shipment.get("plannedDeparture")) or now
    return {
        "node": stages[0]["location"],
        "eta": departure,
        "keptStages": [],
        "mode": "awaiting",
        "note": "Груз ещё не отправлен — планируется весь путь",
    }


def template_attach_index(template: dict, switch_node: str) -> int | None:
    for index, spec in enumerate(template.get("stages") or []):
        if spec["from"] == switch_node:
            return index
    return None


def _attach_context(route: dict, template: dict, ctx: dict) -> dict:
    """Ближайший узел, до которого груз доедет по текущему плану и где начинается шаблон."""
    attach = template_attach_index(template, ctx["node"])
    if attach is not None:
        return {**ctx, "attach": attach}
    kept = list(ctx["keptStages"])
    kept_ids = {stage["id"] for stage in kept}
    for stage in route.get("stages") or []:
        if stage["id"] in kept_ids or stage.get("status") == "completed":
            continue
        kept = kept + [copy.deepcopy(stage)]
        node = stage["nextLocation"]
        attach = template_attach_index(template, node)
        if attach is not None:
            return {
                **ctx,
                "node": node,
                "eta": stage_arrival(stage) or ctx["eta"],
                "keptStages": kept,
                "attach": attach,
                "note": f"Груз доедет до {node} по текущему плану, далее — новый маршрут",
            }
    raise ValueError(
        f"Шаблон «{template['name']}» не стыкуется ни с текущей позицией ({ctx['node']}), "
        "ни с узлами, до которых груз ещё доедет. Сравните другие варианты."
    )


def _materialize_slice(
    template: dict,
    start_index: int,
    departure: datetime,
    route_id: str,
    shipment_id: str,
    stage_offset: int,
) -> list[dict]:
    cursor = departure + timedelta(hours=TRANSFER_BUFFER_HOURS)
    built: list[dict] = []
    for index, spec in enumerate(template["stages"][start_index:], start=stage_offset):
        start = cursor
        if spec["transport"] == "sea":
            buffer_hours = float(spec.get("bufferHours") or 10)
            ship_at = start + timedelta(hours=buffer_hours)
            end = ship_at + timedelta(hours=float(spec["hours"]))
            ship_departure = iso(ship_at)
        else:
            end = start + timedelta(hours=float(spec["hours"]))
            ship_departure = None
        built.append(
            stamp_schedule_on_create(
                {
                    "id": f"{route_id}-{index}",
                    "routeId": route_id,
                    "location": spec["from"],
                    "nextLocation": spec["to"],
                    "transportType": spec["transport"],
                    "plannedStart": iso(start),
                    "plannedArrival": iso(end),
                    "actualArrival": None,
                    "status": "pending",
                    "distanceKm": spec["distanceKm"],
                    "delayHours": 0,
                    "shipDeparture": ship_departure,
                    "description": spec["description"],
                }
            )
        )
        cursor = end
    return built


def _slice_metrics(template: dict, start_index: int) -> tuple[float, int, float]:
    tail = template["stages"][start_index:]
    all_stages = template["stages"]
    tail_distance = sum(float(spec["distanceKm"]) for spec in tail)
    total_distance = sum(float(spec["distanceKm"]) for spec in all_stages) or 1
    tail_hours = sum(float(spec["hours"]) + (float(spec.get("bufferHours") or 0) if spec["transport"] == "sea" else 0) for spec in tail)
    cost = int(round(float(template["cost"]) * tail_distance / total_distance))
    return tail_distance, cost, tail_hours


def build_merged_route(
    shipment: dict,
    route: dict,
    template: dict,
    ctx: dict,
    route_id: str,
    *,
    preview: bool = False,
) -> tuple[dict, dict]:
    if template["destination"] != shipment["destination"]:
        raise ValueError("Альтернатива должна вести в тот же пункт назначения")
    ctx = _attach_context(route, template, ctx)

    attach = ctx["attach"]
    kept = copy.deepcopy(ctx["keptStages"])
    for stage in kept:
        stamp_schedule_on_create(stage)
    offset = len(kept) + 1
    tail = _materialize_slice(template, attach, ctx["eta"], route_id if not preview else "preview", shipment["id"], offset)
    if attach > 0:
        skipped = template["stages"][:attach]
        connector_note = "Пропущены этапы шаблона до узла стыковки: " + "; ".join(
            f"{spec['from']}→{spec['to']}" for spec in skipped
        )
    else:
        connector_note = ""

    extra_leg = ""
    if attach > 0 and template["stages"][attach]["from"] != ctx["node"]:
        extra_leg = f"Стыковка в {ctx['node']}"

    stages = kept + tail
    merged_preview = {"stages": stages}
    if len(kept) < len(stages):
        sync_stage_chain(merged_preview, len(kept))
    tail_distance, tail_cost, tail_hours = _slice_metrics(template, attach)
    full_distance = sum(float(stage.get("distanceKm") or 0) for stage in stages)
    duration = round(tail_hours, 1)

    merged = {
        "id": route_id if not preview else "preview",
        "shipmentId": shipment["id"],
        "name": template["name"],
        "templateId": template["id"],
        "origin": route.get("origin") or template["origin"],
        "destination": template["destination"],
        "stages": stages,
        "distance": round(full_distance, 1),
        "estimatedDuration": duration,
        "estimatedCost": tail_cost if kept else template["cost"],
        "carbonFootprint": route.get("carbonFootprint") or 0,
    }
    meta = {
        "switchNode": ctx["node"],
        "switchEta": iso(ctx["eta"]),
        "switchMode": ctx["mode"],
        "switchNote": ctx["note"],
        "connectorNote": connector_note,
        "metricsScope": "remainder" if kept else "full",
        "remainderDistance": tail_distance,
        "remainderCost": tail_cost,
        "remainderHours": tail_hours,
        "attachIndex": attach,
        "extraLeg": extra_leg,
        "keptCount": len(kept),
    }
    return merged, meta


def _predict_route(shipment: dict, route: dict, data: dict, now: datetime) -> dict:
    from app.services.forecast import forecast

    documents = [doc for doc in data["documents"] if doc["shipmentId"] == shipment["id"]]
    ghost = {**shipment, "destination": route["destination"]}
    port_feeds = (data.get("telemetry") or {}).get("portFeed") or {}
    return forecast(ghost, route, data["ports"], documents, data.get("corridorHistory"), now, port_feeds=port_feeds)


def _option(
    template_id: str,
    name: str,
    sequence: list[str],
    route: dict,
    prediction: dict,
    carbon: dict,
    current: bool,
    meta: dict | None = None,
    *,
    selectable: bool = True,
    unavailable_reason: str | None = None,
    full_carbon: float | None = None,
) -> dict:
    predicted_arrival = prediction.get("predictedArrival") if route.get("stages") else None
    meta = meta or {}
    return {
        "templateId": template_id,
        "name": name,
        "current": current,
        "origin": route["origin"],
        "destination": route["destination"],
        "sequence": sequence,
        "stages": route["stages"],
        "stageCount": len(route["stages"]),
        "distance": meta.get("remainderDistance", route["distance"]) if meta.get("metricsScope") == "remainder" else route["distance"],
        "durationHours": meta.get("remainderHours", route.get("estimatedDuration")) if meta.get("metricsScope") == "remainder" else route_duration_hours(route),
        "cost": meta.get("remainderCost", route["estimatedCost"]) if meta.get("metricsScope") == "remainder" else route["estimatedCost"],
        "probability": prediction["probability"],
        "riskLevel": prediction["riskLevel"],
        "estimatedDelay": prediction["estimatedDelay"],
        "reasons": prediction["reasons"],
        "recommendation": prediction["recommendation"],
        "historyMode": prediction.get("historyMode"),
        "historyMatchCount": prediction.get("historyMatchCount"),
        "carbonFootprint": carbon["total"],
        "carbonByTransport": carbon["byTransport"],
        "predictedArrival": predicted_arrival,
        "metricsScope": meta.get("metricsScope", "full"),
        "switchNode": meta.get("switchNode"),
        "switchEta": meta.get("switchEta"),
        "switchNote": meta.get("switchNote"),
        "connectorNote": meta.get("connectorNote"),
        "fullDistance": route["distance"],
        "fullDurationHours": route_duration_hours(route),
        "fullCost": route["estimatedCost"],
        "fullCarbonFootprint": full_carbon if full_carbon is not None else carbon["total"],
        "selectable": selectable and not current,
        "unavailableReason": unavailable_reason,
        "portRestriction": None,
        "portRestrictionDelayed": False,
    }


def shipment_predicted_eta(last_stage: dict, prediction: dict) -> str | None:
    planned = parse_dt(last_stage.get("plannedArrival"))
    if not planned:
        return None
    return iso(planned + timedelta(hours=float(prediction.get("estimatedDelay") or 0)))


def _template_rate(template: dict | None, route: dict) -> float:
    if template:
        total = sum(float(spec["distanceKm"]) for spec in template["stages"]) or 1
        return float(template["cost"]) / total
    return float(route.get("estimatedCost") or 0) / (float(route.get("distance") or 0) or 1)


def _remaining_scope(
    option: dict,
    stages: list[dict],
    rates: list[float],
    weight: float,
    factors: dict,
    now: datetime,
    from_label: str,
) -> dict:
    open_items = [(stage, rate) for stage, rate in zip(stages, rates) if stage.get("status") != "completed"]
    open_stages = [stage for stage, _ in open_items]
    carbon = calculate(weight, open_stages, factors) if open_stages else {"total": 0, "byTransport": {}}
    arrival = parse_dt(option.get("predictedArrival"))
    option.update(
        {
            "metricsScope": "remaining",
            "scopeLabel": f"Оставшийся путь от {from_label} до {option['destination']}: участков {len(open_stages)}",
            "distance": round(sum(float(stage.get("distanceKm") or 0) for stage in open_stages), 1),
            "cost": int(round(sum(float(stage.get("distanceKm") or 0) * rate for stage, rate in open_items))),
            "durationHours": round(max(0.0, (arrival - now).total_seconds() / 3600), 1) if arrival else option["durationHours"],
            "carbonFootprint": carbon["total"],
            "carbonByTransport": carbon["byTransport"],
            "openStageCount": len(open_stages),
        }
    )
    return option


def _apply_port_flags(option: dict, route: dict, data: dict, now: datetime, *, selectable_default: bool) -> dict:
    feeds = (data.get("telemetry") or {}).get("portFeed") or {}
    summary = route_restriction_summary(route, feeds, now)
    if summary["reasons"]:
        option["portRestriction"] = summary
        option["portRestrictionDelayed"] = summary.get("delayed", False)
    if summary["blocked"] and summary["etaUnknown"]:
        option["selectable"] = False
        option["unavailableReason"] = summary["reason"] or "Маршрут затронут закрытием порта"
    elif selectable_default is False:
        option["selectable"] = False
    return option


def preview_template(data: dict, shipment: dict, route: dict, template: dict, now: datetime) -> dict:
    ctx = switch_context(shipment, route, now)
    try:
        merged, meta = build_merged_route(shipment, route, template, ctx, route["id"], preview=True)
    except ValueError as exc:
        return _option(
            template["id"],
            template["name"],
            template["sequence"],
            {"origin": template["origin"], "destination": template["destination"], "stages": [], "distance": 0, "estimatedCost": 0, "estimatedDuration": 0},
            {"probability": 0, "riskLevel": "none", "estimatedDelay": 0, "reasons": [str(exc)], "recommendation": ""},
            {"total": 0, "byTransport": {}},
            current=False,
            selectable=False,
            unavailable_reason=str(exc),
        )
    prediction = _predict_route(shipment, merged, data, now)
    tail_stages = merged["stages"][meta["keptCount"] :]
    carbon = calculate(float(shipment["weight"]), tail_stages or merged["stages"], data["emissionFactors"])
    merged["estimatedCost"] = meta["remainderCost"] if meta["metricsScope"] == "remainder" else template["cost"]
    full_carbon = calculate(float(shipment["weight"]), merged["stages"], data["emissionFactors"])["total"]
    option = _option(
        template["id"], template["name"], template["sequence"], merged, prediction, carbon,
        current=False, meta=meta, full_carbon=full_carbon,
    )
    rate = _template_rate(template, merged)
    _apply_port_flags(option, merged, data, now, selectable_default=option["selectable"])
    return _remaining_scope(
        option, merged["stages"], [rate] * len(merged["stages"]), float(shipment["weight"]), data["emissionFactors"], now, _position_label(shipment)
    )


def current_option(data: dict, shipment: dict, now: datetime) -> dict:
    route = next(item for item in data["routes"] if item["id"] == shipment["routeId"])
    prediction = next(item for item in data["predictions"] if item["shipmentId"] == shipment["id"])
    ctx = switch_context(shipment, route, now)
    tail = route["stages"][len(ctx["keptStages"]) :]
    scope_stages = tail if tail else route["stages"]
    carbon = calculate(float(shipment["weight"]), scope_stages, data["emissionFactors"])
    template = template_by_id(route.get("templateId", ""))
    sequence = template["sequence"] if template else shipment.get("transportSequence") or []
    meta = {
        "metricsScope": "remainder" if ctx["keptStages"] else "full",
        "switchNode": ctx["node"],
        "switchEta": iso(ctx["eta"]),
        "switchNote": ctx["note"],
        "remainderDistance": sum(float(stage.get("distanceKm") or 0) for stage in tail),
        "remainderCost": route.get("estimatedCost"),
        "remainderHours": route_duration_hours({"stages": tail}) if tail else route_duration_hours(route),
    }
    full_carbon = calculate(float(shipment["weight"]), route["stages"], data["emissionFactors"])["total"]
    option = _option(
        route.get("templateId"), route.get("name") or "Текущий маршрут", sequence, route, prediction, carbon,
        current=True, meta=meta, full_carbon=full_carbon,
    )
    option["predictedArrival"] = shipment.get("predictedArrival")
    option["selectable"] = False
    rate = _template_rate(template, route)
    _apply_port_flags(option, route, data, now, selectable_default=False)
    return _remaining_scope(
        option, route["stages"], [rate] * len(route["stages"]), float(shipment["weight"]),
        data["emissionFactors"], now, _position_label(shipment),
    )


def _position_label(shipment: dict) -> str:
    if shipment.get("status") == "awaiting":
        return f"пункта отправления ({shipment.get('origin')})"
    return f"текущей позиции ({shipment.get('currentLocation') or shipment.get('origin')})"


def options_for_shipment(data: dict, shipment_id: str, now: datetime | None = None) -> list[dict]:
    moment = now or datetime.now().replace(microsecond=0)
    shipment = next(item for item in data["shipments"] if item["id"] == shipment_id)
    route = next(item for item in data["routes"] if item["id"] == shipment["routeId"])
    result = [current_option(data, shipment, moment)]
    for template in ROUTE_TEMPLATES:
        if template["destination"] != shipment["destination"]:
            continue
        if template["id"] == result[0]["templateId"]:
            continue
        if not template_is_valid(template):
            continue
        result.append(preview_template(data, shipment, route, template, moment))
    version = state_version(data, shipment)
    for option in result:
        option["stateVersion"] = version
        if shipment["status"] == "delivered" and option["selectable"]:
            option["selectable"] = False
            option["unavailableReason"] = "Груз уже доставлен"
    return result


def apply_route_alternative(
    data: dict,
    shipment_id: str,
    template_id: str,
    moment: datetime,
    expected_version: str | None = None,
) -> dict:
    """Смена маршрута с сохранением пройденных/активных этапов."""
    shipment = next((item for item in data["shipments"] if item["id"] == shipment_id), None)
    if shipment is None:
        raise ValueError("Груз не найден")
    if shipment["status"] == "delivered":
        raise ValueError("Нельзя сменить маршрут доставленного груза")
    if expected_version and expected_version != state_version(data, shipment):
        raise StaleRouteState(
            "Пока вы сравнивали варианты, по грузу пришли новые данные. Обновите сравнение и выберите снова."
        )
    if template_id == shipment.get("templateId"):
        raise ValueError("Этот маршрут уже выбран")
    template = template_by_id(template_id)
    if template is None or not template_is_valid(template):
        raise ValueError("Нельзя выбрать маршрут без необходимых точек и этапов")
    route = next(item for item in data["routes"] if item["id"] == shipment["routeId"])
    ctx = switch_context(shipment, route, moment)
    merged, meta = build_merged_route(shipment, route, template, ctx, shipment["routeId"], preview=False)
    feeds = (data.get("telemetry") or {}).get("portFeed") or {}
    block = block_apply_reason(merged, feeds, moment)
    if block:
        raise ValueError(block)

    for index, item in enumerate(data["routes"]):
        if item["id"] == shipment["routeId"]:
            data["routes"][index] = {**merged, "estimatedCost": merged["estimatedCost"]}
            break

    shipment["templateId"] = template["id"]
    shipment["transportSequence"] = list(template["sequence"])

    active = next((s for s in merged["stages"] if s.get("status") in ("in_progress", "delayed")), None)
    if active:
        shipment["currentLocation"] = f"перегон {active['location']} — {active['nextLocation']}"
        shipment["currentTransport"] = active["transportType"]
        shipment["currentPort"] = (
            active["location"]
            if active["transportType"] != "rail" and active["location"] in PORT_NAMES
            else None
        )
        if active["status"] == "delayed":
            shipment["status"] = "delayed"
        else:
            shipment["status"] = "in_transit"
    elif ctx["mode"] != "awaiting":
        pending = next((s for s in merged["stages"] if s.get("status") == "pending"), merged["stages"][-1])
        shipment["currentLocation"] = pending["location"]
        shipment["currentTransport"] = pending["transportType"]
        shipment["currentPort"] = pending["location"] if pending["location"] in PORT_NAMES else shipment.get("currentPort")
        shipment["status"] = "in_transit"
    else:
        first = merged["stages"][0]
        shipment["currentLocation"] = first["location"]
        shipment["currentTransport"] = first["transportType"]
        shipment["currentPort"] = first["location"] if first["location"] in PORT_NAMES else None
        shipment["status"] = "awaiting"

    desc = f"Маршрут изменён: {template['name']} (стыковка в {meta['switchNode']})"
    if meta.get("connectorNote"):
        desc += f". {meta['connectorNote']}"
    shipment.setdefault("extraEvents", []).append(
        {
            "time": iso(moment),
            "location": meta["switchNode"],
            "transport": shipment["currentTransport"],
            "description": desc,
            "status": shipment["status"],
        }
    )
    return shipment


class StaleRouteState(ValueError):
    pass


def state_version(data: dict, shipment: dict) -> str:
    """Отпечаток состояния, от которого считались варианты маршрута."""
    import hashlib
    import json

    route = next(item for item in data["routes"] if item["id"] == shipment["routeId"])
    ports = {port["name"]: [port.get("workload"), port.get("windSpeed"), port.get("weatherSeverity")] for port in data["ports"]}
    port_feeds = (data.get("telemetry") or {}).get("portFeed") or {}
    feed_fingerprint = {
        name: [
            feed.get("departureStatus"),
            feed.get("restrictionEndsAt"),
            feed.get("restrictionStartsAt"),
            feed.get("observedAt"),
        ]
        for name, feed in port_feeds.items()
    }
    payload = {
        "shipment": [shipment.get(key) for key in ("status", "currentLocation", "templateId", "plannedArrival")],
        "stages": [
            [
                stage.get(key)
                for key in (
                    "id",
                    "status",
                    "delayHours",
                    "shipDeparture",
                    "actualArrival",
                    "plannedArrival",
                    "schedulePlannedArrival",
                )
            ]
            for stage in route["stages"]
        ],
        "ports": ports,
        "portFeeds": feed_fingerprint,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def point_of(name: str) -> dict:
    return place(name)
