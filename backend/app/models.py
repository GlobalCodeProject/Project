from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


# Devices 
class Device(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True, unique=True)  # e.g., "dc-esp32-1" or "ac-printer-1"
    name: str = "Unnamed"
    kind: str = "dc_sensor"  # "dc_sensor" | "ac_sensor" | "switch"
    location: Optional[str] = None

    # Per-device idle config (overrides global defaults)
    idle_threshold_w: Optional[float] = None
    idle_duration_sec: Optional[int] = None

    # Switch mapping for control (if applicable)
    switch_id: Optional[str] = None
    switch_channel: Optional[str] = None  # e.g. "ch1" or None for single-channel

    # Runtime hints (updated by backend)
    last_seen_at: Optional[datetime] = None
    current_power_w: Optional[float] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

class Approval(SQLModel, table=True):
    __tablename__ = "approvals"

    id: Optional[int] = Field(default=None, primary_key=True)
    channel_id: str = Field(index=True)
    action: str
    state: str
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)

# Telemetry (DC) 
class TelemetryDC(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    voltage_v: float
    current_a: float
    power_w: float
    ts: datetime = Field(default_factory=datetime.utcnow)


# Telemetry (AC) 
class TelemetryAC(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    voltage_v: float
    current_a: float
    power_w: float         # ACTIVE power (already PF-corrected)
    pf: Optional[float] = None
    frequency_hz: Optional[float] = None
    energy_wh: Optional[float] = None
    ts: datetime = Field(default_factory=datetime.utcnow)


#Alerts 
class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    reason: str = "idle_detected"
    threshold_w: float
    duration_s: int
    status: str = "open"  # "open" | "ack" | "snoozed" | "closed"
    ts_open: datetime = Field(default_factory=datetime.utcnow)
    ts_close: Optional[datetime] = None
    snooze_until: Optional[datetime] = None


# Actions (audit)
class Action(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    alert_id: Optional[int] = Field(default=None, index=True)
    device_id: str = Field(index=True)
    action: str  # "shutdown" | "ignore" | "snooze" | "on" | "off" | "ack"
    manager_id: Optional[str] = None
    reason: Optional[str] = None
    ts: datetime = Field(default_factory=datetime.utcnow)
