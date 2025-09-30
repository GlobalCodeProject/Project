from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Device(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True, unique=True)  # e.g., "dc-esp32-1"
    name: str = "Unnamed"
    kind: str = "dc_sensor"  # "dc_sensor" | "ac_sensor" | "switch"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TelemetryDC(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    voltage_v: float
    current_a: float
    power_w: float
    ts: datetime = Field(default_factory=datetime.utcnow)


class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    reason: str = "idle_detected"
    threshold_w: float
    duration_s: int
    status: str = "open"  # "open" | "ack" | "closed"
    ts_open: datetime = Field(default_factory=datetime.utcnow)
    ts_close: Optional[datetime] = None


class Action(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    alert_id: Optional[int] = Field(default=None, index=True)
    device_id: str = Field(index=True)
    action: str  # "shutdown" | "cancel" | "on"
    approved_by: str = "manager@example.com"
    ts: datetime = Field(default_factory=datetime.utcnow)
