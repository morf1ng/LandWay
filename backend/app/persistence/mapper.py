"""Загрузка и сохранение состояния приложения в PostgreSQL."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.catalog import DEFAULT_EMISSION_FACTORS
from app.models import (
    AppMetaRow,
    DocumentRow,
    JournalRow,
    NotificationRow,
    PortRow,
    RiskPredictionRow,
    RouteRow,
    RouteStageRow,
    SessionRow,
    ShipmentRow,
    UserRow,
)


def _shipment_to_dict(row: ShipmentRow) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "category": row.category,
        "weight": row.weight,
        "containerCount": row.container_count,
        "sender": row.sender,
        "receiver": row.receiver,
        "origin": row.origin,
        "destination": row.destination,
        "status": row.status,
        "plannedDeparture": row.planned_departure,
        "plannedArrival": row.planned_arrival,
        "predictedArrival": row.predicted_arrival,
        "currentLocation": row.current_location,
        "currentPort": row.current_port,
        "currentTransport": row.current_transport,
        "routeId": row.route_id,
        "templateId": row.template_id,
        "transportSequence": list(row.transport_sequence or []),
        "riskScore": row.risk_score,
        "notes": row.notes or "",
        "preclearanceStatus": row.preclearance_status,
        "preclearanceAt": row.preclearance_at,
        "extraEvents": list(row.extra_events or []),
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


def _shipment_from_dict(data: dict) -> dict:
    return {
        "id": data["id"],
        "name": data["name"],
        "category": data["category"],
        "weight": data["weight"],
        "container_count": data["containerCount"],
        "sender": data["sender"],
        "receiver": data["receiver"],
        "origin": data["origin"],
        "destination": data["destination"],
        "status": data["status"],
        "planned_departure": data["plannedDeparture"],
        "planned_arrival": data["plannedArrival"],
        "predicted_arrival": data["predictedArrival"],
        "current_location": data["currentLocation"],
        "current_port": data.get("currentPort"),
        "current_transport": data["currentTransport"],
        "route_id": data["routeId"],
        "template_id": data.get("templateId") or "",
        "transport_sequence": data.get("transportSequence") or [],
        "risk_score": data.get("riskScore") or 0,
        "notes": data.get("notes") or "",
        "preclearance_status": data.get("preclearanceStatus"),
        "preclearance_at": data.get("preclearanceAt"),
        "extra_events": data.get("extraEvents") or [],
        "created_at": data.get("createdAt") or data["plannedDeparture"],
        "updated_at": data.get("updatedAt") or data["plannedDeparture"],
    }


def _stage_to_dict(row: RouteStageRow) -> dict:
    return {
        "id": row.id,
        "routeId": row.route_id,
        "location": row.location,
        "nextLocation": row.next_location,
        "transportType": row.transport_type,
        "plannedStart": row.planned_start,
        "plannedArrival": row.planned_arrival,
        "actualArrival": row.actual_arrival,
        "status": row.status,
        "distanceKm": row.distance_km,
        "delayHours": row.delay_hours,
        "shipDeparture": row.ship_departure,
        "description": row.description,
    }


def _port_to_dict(row: PortRow) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "location": row.location,
        "lat": row.lat,
        "lon": row.lon,
        "x": row.x,
        "y": row.y,
        "workload": row.workload,
        "weather": row.weather,
        "weatherSeverity": row.weather_severity,
        "windSpeed": row.wind_speed,
        "delayRisk": row.delay_risk,
    }


def load_state(session: Session) -> dict:
    shipments = [_shipment_to_dict(row) for row in session.scalars(select(ShipmentRow)).all()]
    routes = []
    for route in session.scalars(select(RouteRow).options(selectinload(RouteRow.stages))).all():
        routes.append(
            {
                "id": route.id,
                "shipmentId": route.shipment_id,
                "name": route.name,
                "templateId": route.template_id,
                "origin": route.origin,
                "destination": route.destination,
                "distance": route.distance,
                "estimatedDuration": route.estimated_duration,
                "estimatedCost": route.estimated_cost,
                "carbonFootprint": route.carbon_footprint,
                "stages": [_stage_to_dict(stage) for stage in route.stages],
            }
        )

    predictions = []
    for row in session.scalars(select(RiskPredictionRow)).all():
        predictions.append(
            {
                "id": row.id,
                "shipmentId": row.shipment_id,
                "probability": row.probability,
                "riskLevel": row.risk_level,
                "reasons": list(row.reasons or []),
                "estimatedDelay": row.estimated_delay,
                "recommendation": row.recommendation,
                "calculatedAt": row.calculated_at,
            }
        )

    documents = []
    for row in session.scalars(select(DocumentRow)).all():
        documents.append(
            {
                "id": row.id,
                "shipmentId": row.shipment_id,
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "uploadedAt": row.uploaded_at,
                "comment": row.comment,
                "file": row.file_meta,
                "fields": dict(row.fields or {}),
            }
        )

    notifications = []
    for row in session.scalars(select(NotificationRow)).all():
        notifications.append(
            {
                "id": row.id,
                "shipmentId": row.shipment_id,
                "type": row.type,
                "title": row.title,
                "description": row.description,
                "severity": row.severity,
                "createdAt": row.created_at,
                "read": row.read,
                "href": row.href,
            }
        )

    journal = []
    for row in session.scalars(select(JournalRow).order_by(JournalRow.at.desc())).all():
        journal.append(
            {
                "id": row.id,
                "shipmentId": row.shipment_id,
                "type": row.type,
                "title": row.title,
                "result": row.result,
                "details": row.details,
                "at": row.at,
            }
        )

    ports = [_port_to_dict(row) for row in session.scalars(select(PortRow)).all()]

    users = []
    for row in session.scalars(select(UserRow)).all():
        users.append(
            {
                "id": row.id,
                "username": row.username,
                "passwordHash": row.password_hash,
                "name": row.name,
                "role": row.role,
                "organization": row.organization,
            }
        )

    sessions = []
    for row in session.scalars(select(SessionRow)).all():
        sessions.append(
            {
                "token": row.token,
                "userId": row.user_id,
                "createdAt": row.created_at,
                "expiresAt": row.expires_at,
            }
        )

    meta_row = session.get(AppMetaRow, "settings")
    settings = (meta_row.value if meta_row else {}) or {}
    emission = settings.get("emissionFactors") or dict(DEFAULT_EMISSION_FACTORS)
    profile = settings.get("profile") or {}
    last_recalc = settings.get("lastRecalculatedAt")

    return {
        "shipments": shipments,
        "routes": routes,
        "predictions": predictions,
        "documents": documents,
        "notifications": notifications,
        "journal": journal,
        "ports": ports,
        "emissionFactors": emission,
        "users": users,
        "sessions": sessions,
        "profile": profile,
        "lastRecalculatedAt": last_recalc,
        "corridorChain": settings.get("corridorChain") or [],
    }


def save_state(session: Session, data: dict) -> None:
    shipment_ids = {item["id"] for item in data["shipments"]}
    existing_shipments = set(session.scalars(select(ShipmentRow.id)).all())
    for sid in existing_shipments - shipment_ids:
        session.delete(session.get(ShipmentRow, sid))

    for item in data["shipments"]:
        payload = _shipment_from_dict(item)
        row = session.get(ShipmentRow, item["id"])
        if row is None:
            row = ShipmentRow(**payload)
            session.add(row)
        else:
            for key, value in payload.items():
                setattr(row, key, value)

    session.flush()

    route_ids = {item["id"] for item in data["routes"]}
    existing_routes = set(session.scalars(select(RouteRow.id)).all())
    for rid in existing_routes - route_ids:
        session.delete(session.get(RouteRow, rid))

    stage_ids = set()
    for item in data["routes"]:
        row = session.get(RouteRow, item["id"])
        stages = item.get("stages") or []
        if row is None:
            row = RouteRow(
                id=item["id"],
                shipment_id=item["shipmentId"],
                name=item.get("name") or "",
                template_id=item.get("templateId") or "",
                origin=item["origin"],
                destination=item["destination"],
                distance=item.get("distance") or 0,
                estimated_duration=item.get("estimatedDuration") or 0,
                estimated_cost=item.get("estimatedCost") or 0,
                carbon_footprint=item.get("carbonFootprint") or 0,
            )
            session.add(row)
            session.flush()
        else:
            row.shipment_id = item["shipmentId"]
            row.name = item.get("name") or ""
            row.template_id = item.get("templateId") or ""
            row.origin = item["origin"]
            row.destination = item["destination"]
            row.distance = item.get("distance") or 0
            row.estimated_duration = item.get("estimatedDuration") or 0
            row.estimated_cost = item.get("estimatedCost") or 0
            row.carbon_footprint = item.get("carbonFootprint") or 0

        existing_stage_ids = {s.id for s in (row.stages if row else [])}
        new_stage_ids = {stage["id"] for stage in stages}
        for sid in existing_stage_ids - new_stage_ids:
            session.delete(session.get(RouteStageRow, sid))

        for stage in stages:
            stage_ids.add(stage["id"])
            srow = session.get(RouteStageRow, stage["id"])
            payload = {
                "id": stage["id"],
                "route_id": item["id"],
                "location": stage["location"],
                "next_location": stage["nextLocation"],
                "transport_type": stage["transportType"],
                "planned_start": stage["plannedStart"],
                "planned_arrival": stage["plannedArrival"],
                "actual_arrival": stage.get("actualArrival"),
                "status": stage["status"],
                "distance_km": stage.get("distanceKm") or 0,
                "delay_hours": stage.get("delayHours") or 0,
                "ship_departure": stage.get("shipDeparture"),
                "description": stage.get("description") or "",
            }
            if srow is None:
                session.add(RouteStageRow(**payload))
            else:
                for key, value in payload.items():
                    setattr(srow, key, value)

    session.execute(delete(RiskPredictionRow))
    for item in data["predictions"]:
        session.add(
            RiskPredictionRow(
                id=item["id"],
                shipment_id=item["shipmentId"],
                probability=item["probability"],
                risk_level=item["riskLevel"],
                reasons=item.get("reasons") or [],
                estimated_delay=item.get("estimatedDelay") or 0,
                recommendation=item.get("recommendation") or "",
                calculated_at=item["calculatedAt"],
            )
        )

    doc_ids = {item["id"] for item in data["documents"]}
    for did in set(session.scalars(select(DocumentRow.id)).all()) - doc_ids:
        session.delete(session.get(DocumentRow, did))
    for item in data["documents"]:
        row = session.get(DocumentRow, item["id"])
        payload = {
            "id": item["id"],
            "shipment_id": item["shipmentId"],
            "name": item["name"],
            "type": item["type"],
            "status": item["status"],
            "uploaded_at": item.get("uploadedAt"),
            "comment": item.get("comment") or "",
            "file_meta": item.get("file"),
            "fields": item.get("fields") or {},
        }
        if row is None:
            session.add(DocumentRow(**payload))
        else:
            for key, value in payload.items():
                setattr(row, key, value)

    session.execute(delete(NotificationRow))
    for item in data["notifications"]:
        session.add(
            NotificationRow(
                id=item["id"],
                shipment_id=item.get("shipmentId"),
                type=item["type"],
                title=item["title"],
                description=item["description"],
                severity=item["severity"],
                created_at=item["createdAt"],
                read=bool(item.get("read")),
                href=item.get("href") or "",
            )
        )

    journal_ids = {item["id"] for item in data["journal"]}
    for jid in set(session.scalars(select(JournalRow.id)).all()) - journal_ids:
        session.delete(session.get(JournalRow, jid))
    for item in data["journal"]:
        row = session.get(JournalRow, item["id"])
        payload = {
            "id": item["id"],
            "shipment_id": item.get("shipmentId"),
            "type": item["type"],
            "title": item["title"],
            "result": item["result"],
            "details": item["details"],
            "at": item["at"],
        }
        if row is None:
            session.add(JournalRow(**payload))
        else:
            for key, value in payload.items():
                setattr(row, key, value)

    for item in data["ports"]:
        row = session.get(PortRow, item["id"])
        payload = {
            "id": item["id"],
            "name": item["name"],
            "location": item.get("location") or "",
            "lat": item.get("lat") or 0,
            "lon": item.get("lon") or 0,
            "x": item.get("x") or 0,
            "y": item.get("y") or 0,
            "workload": item.get("workload") or 0,
            "weather": item.get("weather") or "",
            "weather_severity": item.get("weatherSeverity") or "clear",
            "wind_speed": item.get("windSpeed") or 0,
            "delay_risk": item.get("delayRisk") or "low",
        }
        if row is None:
            session.add(PortRow(**payload))
        else:
            for key, value in payload.items():
                setattr(row, key, value)

    db_users = {row.id: row for row in session.scalars(select(UserRow)).all()}
    seen_users = set()
    for item in data["users"]:
        seen_users.add(item["id"])
        row = db_users.get(item["id"])
        payload = {
            "id": item["id"],
            "username": item["username"],
            "password_hash": item["passwordHash"],
            "name": item["name"],
            "role": item["role"],
            "organization": item["organization"],
        }
        if row is None:
            session.add(UserRow(**payload))
        else:
            for key, value in payload.items():
                setattr(row, key, value)
    for uid in set(db_users) - seen_users:
        session.delete(db_users[uid])

    session.execute(delete(SessionRow))
    for item in data["sessions"]:
        session.add(
            SessionRow(
                token=item["token"],
                user_id=item["userId"],
                created_at=item["createdAt"],
                expires_at=item["expiresAt"],
            )
        )

    settings = {
        "emissionFactors": data.get("emissionFactors") or dict(DEFAULT_EMISSION_FACTORS),
        "profile": data.get("profile") or {},
        "lastRecalculatedAt": data.get("lastRecalculatedAt"),
        "corridorChain": data.get("corridorChain") or [],
    }
    meta = session.get(AppMetaRow, "settings")
    if meta is None:
        session.add(AppMetaRow(key="settings", value=settings))
    else:
        meta.value = settings
