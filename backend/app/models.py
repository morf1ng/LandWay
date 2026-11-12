"""Схема SQLAlchemy для будущего PostgreSQL.

Таблицы повторяют сущности прототипа. Сейчас приложение их не читает
и не пишет: рабочие данные лежат в JSON-хранилище.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ShipmentRow(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(255))
    weight: Mapped[float] = mapped_column(Float)
    container_count: Mapped[int] = mapped_column(Integer)
    sender: Mapped[str] = mapped_column(String(255))
    receiver: Mapped[str] = mapped_column(String(255))
    origin: Mapped[str] = mapped_column(String(128))
    destination: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(64))
    planned_departure: Mapped[str] = mapped_column(String(40))
    planned_arrival: Mapped[str] = mapped_column(String(40))
    predicted_arrival: Mapped[str] = mapped_column(String(40))
    current_location: Mapped[str] = mapped_column(String(255))
    current_transport: Mapped[str] = mapped_column(String(32))
    route_id: Mapped[str] = mapped_column(String(64))
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")


class RouteRow(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    origin: Mapped[str] = mapped_column(String(128))
    destination: Mapped[str] = mapped_column(String(128))
    distance: Mapped[float] = mapped_column(Float, default=0)
    estimated_duration: Mapped[float] = mapped_column(Float, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    carbon_footprint: Mapped[float] = mapped_column(Float, default=0)
    stages: Mapped[list["RouteStageRow"]] = relationship(back_populates="route")


class RouteStageRow(Base):
    __tablename__ = "route_stages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"))
    location: Mapped[str] = mapped_column(String(128))
    transport_type: Mapped[str] = mapped_column(String(32))
    planned_arrival: Mapped[str] = mapped_column(String(40))
    actual_arrival: Mapped[str] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    route: Mapped[RouteRow] = relationship(back_populates="stages")


class RiskPredictionRow(Base):
    __tablename__ = "risk_predictions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    probability: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(16))
    reasons: Mapped[str] = mapped_column(Text, default="")
    estimated_delay: Mapped[float] = mapped_column(Float, default=0)
    recommendation: Mapped[str] = mapped_column(Text, default="")
    calculated_at: Mapped[str] = mapped_column(String(40))


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    uploaded_at: Mapped[str] = mapped_column(String(40), nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")


class PortRow(Base):
    __tablename__ = "ports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    location: Mapped[str] = mapped_column(String(255))
    workload: Mapped[float] = mapped_column(Float)
    weather: Mapped[str] = mapped_column(String(255))
    wind_speed: Mapped[float] = mapped_column(Float)
    delay_risk: Mapped[str] = mapped_column(String(16))


class NotificationRow(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(String(32), nullable=True)
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[str] = mapped_column(String(40))
    read: Mapped[int] = mapped_column(Integer, default=0)


class EnvironmentalRow(Base):
    __tablename__ = "environmental_data"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    transport_type: Mapped[str] = mapped_column(String(32))
    distance: Mapped[float] = mapped_column(Float)
    cargo_weight: Mapped[float] = mapped_column(Float)
    emission_factor: Mapped[float] = mapped_column(Float)
    co2_emission: Mapped[float] = mapped_column(Float)
