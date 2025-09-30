from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from sqlalchemy import func
from ..models import Device, TelemetryDC, TelemetryAC


router = APIRouter()


# ---------- Schemas ----------
class DeviceUpsert(BaseModel):
    device_id: str
    name: str = "Unnamed"
    kind: str = "dc_sensor"  # "dc_sensor" | "ac_sensor" | "switch"
    location: Optional[str] = None
    idle_threshold_w: Optional[float] = None
    idle_duration_sec: Optional[int] = None
    switch_id: Optional[str] = None
    switch_channel: Optional[str] = None


class DeviceRow(BaseModel):
    device_id: str
    name: str
    kind: str
    location: Optional[str]
    current_power_w: Optional[float]
    avg_1m_w: Optional[float]
    avg_5m_w: Optional[float]
    avg_10m_w: Optional[float]
    idle: bool


# ---------- Helpers ----------
def _tables_for(kind: str):
    if kind == "dc_sensor":
        return TelemetryDC
    elif kind == "ac_sensor":
        return TelemetryAC
    return None  # switches don't produce telemetry


def _latest_power(session: Session, table, device_id: str) -> Optional[float]:
    row = session.exec(
        select(table.power_w)
        .where(table.device_id == device_id)
        .order_by(table.ts.desc())
        .limit(1)
    ).first()
    return float(row) if row is not None else None


def _avg_power_since(session: Session, table, device_id: str, since: datetime) -> Optional[float]:
    avg_val = session.exec(
        select(func.avg(table.power_w))
        .where(table.device_id == device_id, table.ts >= since)
    ).first()
    return float(avg_val) if avg_val is not None else None


def _rolling_averages(session: Session, table, device_id: str) -> Tuple[
    Optional[float], Optional[float], Optional[float]]:
    now = datetime.utcnow()
    return (
        _avg_power_since(session, table, device_id, now - timedelta(minutes=1)),
        _avg_power_since(session, table, device_id, now - timedelta(minutes=5)),
        _avg_power_since(session, table, device_id, now - timedelta(minutes=10)),
    )


# ---------- Routes ----------
@router.get("")  # /devices
@router.get("/")  # /devices/
def list_devices(request: Request) -> List[DeviceRow]:
    engine = request.app.state.engine
    detector = request.app.state.detector  # reads per-device overrides

    rows: List[DeviceRow] = []
    with Session(engine) as s:
        devices = s.exec(select(Device)).all()  # DB is the source of truth :contentReference[oaicite:2]{index=2}
        for d in devices:
            table = _tables_for(d.kind)

            if not table:  # e.g., "switch" device
                rows.append(DeviceRow(
                    device_id=d.device_id, name=d.name, kind=d.kind, location=d.location,
                    current_power_w=None, avg_1m_w=None, avg_5m_w=None, avg_10m_w=None, idle=False
                ))
                continue

            current_w = _latest_power(s, table, d.device_id)
            avg_1m, avg_5m, avg_10m = _rolling_averages(s, table, d.device_id)

            th, _du = detector._cfg(d.device_id)
            basis = avg_5m if (avg_5m is not None) else (current_w or 0.0)
            is_idle = basis < (th or 0.0)

            rows.append(DeviceRow(
                device_id=d.device_id,
                name=d.name,
                kind=d.kind,
                location=d.location,
                current_power_w=current_w,
                avg_1m_w=avg_1m,
                avg_5m_w=avg_5m,
                avg_10m_w=avg_10m,
                idle=bool(is_idle),
            ))
    return rows


@router.post("")  # /devices
@router.post("/")  # /devices/
def upsert_device(body: DeviceUpsert, request: Request):
    engine = request.app.state.engine
    detector = request.app.state.detector

    # Work with the object inside the session and capture simple values
    with Session(engine) as s:
        d = s.exec(select(Device).where(Device.device_id == body.device_id)).first()
        if not d:
            d = Device(device_id=body.device_id)
        d.name = body.name
        d.kind = body.kind
        d.location = body.location
        d.idle_threshold_w = body.idle_threshold_w
        d.idle_duration_sec = body.idle_duration_sec
        d.switch_id = body.switch_id
        d.switch_channel = body.switch_channel
        s.add(d)
        s.commit()  # after this, attributes are expired by default (see note below) :contentReference[oaicite:3]{index=3}

        # capture plain values while session is still open (or call detector inside)
        thr = d.idle_threshold_w
        dur = d.idle_duration_sec

    detector.set_overrides(body.device_id, thr, dur)  # safe: using plain values
    return {"ok": True}


class DeviceConfigPatch(BaseModel):
    idle_threshold_w: Optional[float] = None
    idle_duration_sec: Optional[int] = None


@router.patch("/{device_id}/config")
@router.patch("/{device_id}/config/")
def patch_config(device_id: str, body: DeviceConfigPatch, request: Request):
    engine = request.app.state.engine
    detector = request.app.state.detector
    with Session(engine) as s:
        d = s.exec(select(Device).where(Device.device_id == device_id)).first()
        if not d:
            raise HTTPException(status_code=404, detail="device not found")
        if body.idle_threshold_w is not None:
            d.idle_threshold_w = body.idle_threshold_w
        if body.idle_duration_sec is not None:
            d.idle_duration_sec = body.idle_duration_sec
        s.add(d)
        s.commit()
        thr = d.idle_threshold_w
        dur = d.idle_duration_sec
    detector.set_overrides(device_id, thr, dur)
    return {"ok": True}


class CommandBody(BaseModel):
    action: str  # "on" | "off"


@router.post("/{device_id}/command")
@router.post("/{device_id}/command/")
def device_command(device_id: str, body: CommandBody, request: Request):
    publish = request.app.state.publish_switch
    engine = request.app.state.engine
    with Session(engine) as s:
        d = s.exec(select(Device).where(Device.device_id == device_id)).first()
        if not d:
            raise HTTPException(status_code=404, detail="device not found")
        if not d.switch_id:
            raise HTTPException(status_code=400, detail="device has no switch mapping")
        state = "ON" if body.action.lower() == "on" else "OFF"
        publish(d.switch_id, state, d.switch_channel)
        return {"ok": True, "published": {"switch_id": d.switch_id, "channel": d.switch_channel, "state": state}}


router = APIRouter()


# ---------- Schemas ----------
class DeviceUpsert(BaseModel):
    device_id: str
    name: str = "Unnamed"
    kind: str = "dc_sensor"  # "dc_sensor" | "ac_sensor" | "switch"
    location: Optional[str] = None
    idle_threshold_w: Optional[float] = None
    idle_duration_sec: Optional[int] = None
    switch_id: Optional[str] = None
    switch_channel: Optional[str] = None


class DeviceRow(BaseModel):
    device_id: str
    name: str
    kind: str
    location: Optional[str]
    current_power_w: Optional[float]
    avg_1m_w: Optional[float]
    avg_5m_w: Optional[float]
    avg_10m_w: Optional[float]
    idle: bool


# ---------- Helpers ----------
def _tables_for(kind: str):
    if kind == "dc_sensor":
        return TelemetryDC
    elif kind == "ac_sensor":
        return TelemetryAC
    return None  # switches don't produce telemetry


def _latest_power(session: Session, table, device_id: str) -> Optional[float]:
    row = session.exec(
        select(table.power_w)
        .where(table.device_id == device_id)
        .order_by(table.ts.desc())
        .limit(1)
    ).first()
    return float(row) if row is not None else None


def _avg_power_since(session: Session, table, device_id: str, since: datetime) -> Optional[float]:
    avg_val = session.exec(
        select(func.avg(table.power_w))
        .where(table.device_id == device_id, table.ts >= since)
    ).first()
    return float(avg_val) if avg_val is not None else None


def _rolling_averages(session: Session, table, device_id: str) -> Tuple[
    Optional[float], Optional[float], Optional[float]]:
    now = datetime.utcnow()
    return (
        _avg_power_since(session, table, device_id, now - timedelta(minutes=1)),
        _avg_power_since(session, table, device_id, now - timedelta(minutes=5)),
        _avg_power_since(session, table, device_id, now - timedelta(minutes=10)),
    )


# ---------- Routes ----------
@router.get("")  # /devices
@router.get("/")  # /devices/
def list_devices(request: Request) -> List[DeviceRow]:
    engine = request.app.state.engine
    detector = request.app.state.detector  # reads per-device overrides

    rows: List[DeviceRow] = []
    with Session(engine) as s:
        devices = s.exec(select(Device)).all()  # DB is the source of truth :contentReference[oaicite:2]{index=2}
        for d in devices:
            table = _tables_for(d.kind)

            if not table:  # e.g., "switch" device
                rows.append(DeviceRow(
                    device_id=d.device_id, name=d.name, kind=d.kind, location=d.location,
                    current_power_w=None, avg_1m_w=None, avg_5m_w=None, avg_10m_w=None, idle=False
                ))
                continue

            current_w = _latest_power(s, table, d.device_id)
            avg_1m, avg_5m, avg_10m = _rolling_averages(s, table, d.device_id)

            th, _du = detector._cfg(d.device_id)
            basis = avg_5m if (avg_5m is not None) else (current_w or 0.0)
            is_idle = basis < (th or 0.0)

            rows.append(DeviceRow(
                device_id=d.device_id,
                name=d.name,
                kind=d.kind,
                location=d.location,
                current_power_w=current_w,
                avg_1m_w=avg_1m,
                avg_5m_w=avg_5m,
                avg_10m_w=avg_10m,
                idle=bool(is_idle),
            ))
    return rows


@router.post("")  # /devices
@router.post("/")  # /devices/
def upsert_device(body: DeviceUpsert, request: Request):
    engine = request.app.state.engine
    detector = request.app.state.detector

    # Work with the object inside the session and capture simple values
    with Session(engine) as s:
        d = s.exec(select(Device).where(Device.device_id == body.device_id)).first()
        if not d:
            d = Device(device_id=body.device_id)
        d.name = body.name
        d.kind = body.kind
        d.location = body.location
        d.idle_threshold_w = body.idle_threshold_w
        d.idle_duration_sec = body.idle_duration_sec
        d.switch_id = body.switch_id
        d.switch_channel = body.switch_channel
        s.add(d)
        s.commit()  # after this, attributes are expired by default (see note below) :contentReference[oaicite:3]{index=3}

        # capture plain values while session is still open (or call detector inside)
        thr = d.idle_threshold_w
        dur = d.idle_duration_sec

    detector.set_overrides(body.device_id, thr, dur)  # safe: using plain values
    return {"ok": True}


class DeviceConfigPatch(BaseModel):
    idle_threshold_w: Optional[float] = None
    idle_duration_sec: Optional[int] = None


@router.patch("/{device_id}/config")
@router.patch("/{device_id}/config/")
def patch_config(device_id: str, body: DeviceConfigPatch, request: Request):
    engine = request.app.state.engine
    detector = request.app.state.detector
    with Session(engine) as s:
        d = s.exec(select(Device).where(Device.device_id == device_id)).first()
        if not d:
            raise HTTPException(status_code=404, detail="device not found")
        if body.idle_threshold_w is not None:
            d.idle_threshold_w = body.idle_threshold_w
        if body.idle_duration_sec is not None:
            d.idle_duration_sec = body.idle_duration_sec
        s.add(d)
        s.commit()
        thr = d.idle_threshold_w
        dur = d.idle_duration_sec
    detector.set_overrides(device_id, thr, dur)
    return {"ok": True}


class CommandBody(BaseModel):
    action: str  # "on" | "off"


@router.post("/{device_id}/command")
@router.post("/{device_id}/command/")
def device_command(device_id: str, body: CommandBody, request: Request):
    publish = request.app.state.publish_switch
    engine = request.app.state.engine
    with Session(engine) as s:
        d = s.exec(select(Device).where(Device.device_id == device_id)).first()
        if not d:
            raise HTTPException(status_code=404, detail="device not found")
        if not d.switch_id:
            raise HTTPException(status_code=400, detail="device has no switch mapping")
        state = "ON" if body.action.lower() == "on" else "OFF"
        publish(d.switch_id, state, d.switch_channel)
        return {"ok": True, "published": {"switch_id": d.switch_id, "channel": d.switch_channel, "state": state}}
