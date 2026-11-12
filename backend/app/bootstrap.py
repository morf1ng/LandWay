"""Первичная инициализация БД: пользователи, порты, настройки. Без демо-грузов."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog import DEFAULT_EMISSION_FACTORS, PORTS
from app.models import AppMetaRow, PortRow, UserRow
from app.demo_data import seed_demo_if_empty
from app.services.auth import default_users


def ensure_bootstrap(session: Session) -> None:
    user_count = session.scalar(select(func.count()).select_from(UserRow))
    if not user_count:
        for user in default_users():
            session.add(
                UserRow(
                    id=user["id"],
                    username=user["username"],
                    password_hash=user["passwordHash"],
                    name=user["name"],
                    role=user["role"],
                    organization=user["organization"],
                )
            )

    port_count = session.scalar(select(func.count()).select_from(PortRow))
    if not port_count:
        for port in PORTS:
            session.add(
                PortRow(
                    id=port["id"],
                    name=port["name"],
                    location=port["location"],
                    lat=port["lat"],
                    lon=port["lon"],
                    x=port["x"],
                    y=port["y"],
                    workload=port["workload"],
                    weather=port["weather"],
                    weather_severity=port["weatherSeverity"],
                    wind_speed=port["windSpeed"],
                    delay_risk=port["delayRisk"],
                )
            )

    meta = session.get(AppMetaRow, "settings")
    if meta is None:
        first = default_users()[0]
        session.add(
            AppMetaRow(
                key="settings",
                value={
                    "emissionFactors": dict(DEFAULT_EMISSION_FACTORS),
                    "lastRecalculatedAt": None,
                    "profile": {
                        "name": first["name"],
                        "role": first["role"],
                        "organization": first["organization"],
                        "userId": first["id"],
                    },
                },
            )
        )

    session.commit()
    seed_demo_if_empty(session)
