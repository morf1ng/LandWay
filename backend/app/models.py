"""SQLAlchemy-модели PostgreSQL для Smart Caspian Transit."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(255))
    organization: Mapped[str] = mapped_column(String(255))


class SessionRow(Base):
    __tablename__ = "auth_sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    expires_at: Mapped[str] = mapped_column(String(40))


class AppMetaRow(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)


class PortRow(Base):
    __tablename__ = "ports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    location: Mapped[str] = mapped_column(String(255))
    lat: Mapped[float] = mapped_column(Float, default=0)
    lon: Mapped[float] = mapped_column(Float, default=0)
    x: Mapped[float] = mapped_column(Float, default=0)
    y: Mapped[float] = mapped_column(Float, default=0)
    workload: Mapped[float] = mapped_column(Float, default=50)
    weather: Mapped[str] = mapped_column(String(255), default="")
    weather_severity: Mapped[str] = mapped_column(String(32), default="clear")
    wind_speed: Mapped[float] = mapped_column(Float, default=0)
    delay_risk: Mapped[str] = mapped_column(String(16), default="low")


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
    predicted_arrival: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_location: Mapped[str] = mapped_column(String(255))
    current_port: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_transport: Mapped[str] = mapped_column(String(32))
    route_id: Mapped[str] = mapped_column(String(64))
    template_id: Mapped[str] = mapped_column(String(64), default="")
    transport_sequence: Mapped[list] = mapped_column(JSONB, default=list)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    preclearance_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preclearance_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    extra_events: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class RouteRow(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    template_id: Mapped[str] = mapped_column(String(64), default="")
    origin: Mapped[str] = mapped_column(String(128))
    destination: Mapped[str] = mapped_column(String(128))
    distance: Mapped[float] = mapped_column(Float, default=0)
    estimated_duration: Mapped[float] = mapped_column(Float, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    carbon_footprint: Mapped[float] = mapped_column(Float, default=0)
    stages: Mapped[list["RouteStageRow"]] = relationship(back_populates="route", cascade="all, delete-orphan")


class RouteStageRow(Base):
    __tablename__ = "route_stages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), index=True)
    location: Mapped[str] = mapped_column(String(128))
    next_location: Mapped[str] = mapped_column(String(128))
    transport_type: Mapped[str] = mapped_column(String(32))
    planned_start: Mapped[str] = mapped_column(String(40))
    planned_arrival: Mapped[str] = mapped_column(String(40))
    schedule_planned_start: Mapped[str | None] = mapped_column(String(40), nullable=True)
    schedule_planned_arrival: Mapped[str | None] = mapped_column(String(40), nullable=True)
    schedule_ship_departure: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actual_arrival: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    distance_km: Mapped[float] = mapped_column(Float, default=0)
    delay_hours: Mapped[float] = mapped_column(Float, default=0)
    ship_departure: Mapped[str | None] = mapped_column(String(40), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    route: Mapped[RouteRow] = relationship(back_populates="stages")


class RiskPredictionRow(Base):
    __tablename__ = "risk_predictions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), unique=True)
    probability: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(16))
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    estimated_delay: Mapped[float] = mapped_column(Float, default=0)
    recommendation: Mapped[str] = mapped_column(Text, default="")
    calculated_at: Mapped[str] = mapped_column(String(40))


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    uploaded_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    file_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fields: Mapped[dict] = mapped_column(JSONB, default=dict)


class NotificationRow(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[str] = mapped_column(String(40))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    href: Mapped[str] = mapped_column(String(255), default="")


class JournalRow(Base):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    result: Mapped[str] = mapped_column(String(255))
    details: Mapped[str] = mapped_column(Text)
    at: Mapped[str] = mapped_column(String(40))


class EnvironmentalRow(Base):
    __tablename__ = "environmental_data"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"))
    transport_type: Mapped[str] = mapped_column(String(32))
    distance: Mapped[float] = mapped_column(Float)
    cargo_weight: Mapped[float] = mapped_column(Float)
    emission_factor: Mapped[float] = mapped_column(Float)
    co2_emission: Mapped[float] = mapped_column(Float)
