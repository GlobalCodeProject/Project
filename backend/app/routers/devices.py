from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from ..models import Device

router = APIRouter()

# publish function is injected via app.state.publish_switch

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

@router.get("/", response_model=List[DeviceRow])
def list_devices(request: Request):
    engine = request.app.state.engine
    rolling = request.app.state.rolling
    detector = request.app.state.detector
    latest_dc = request.app.state.latest_dc
    latest_ac = request.app.state.latest_ac

    rows: List[DeviceRow] = []
    with Session(engine) as s:
        devices = s.exec(select(Device)).all()
        for d in devices:
            p = None
            if d.kind == "dc_sensor" and d.device_id in latest_dc:
                p = latest_dc[d.device_id].get("p")
            elif d.kind == "ac_sensor" and d.device_id in latest_ac:
                p = latest_ac[d.device_id].get("p")

            stats = rolling.stats(d.device_id)
            th, _du = detector._cfg(d.device_id)
            avg = stats.get("avg_5m_w") or p or 0.0
            idle = (avg is not None) and (avg < th)

            rows.append(DeviceRow(
                device_id=d.device_id,
                name=d.name,
                kind=d.kind,
                location=d.location,
                current_power_w=p,
                avg_1m_w=stats.get("avg_1m_w"),
                avg_5m_w=stats.get("avg_5m_w"),
                avg_10m_w=stats.get("avg_10m_w"),
                idle=bool(idle),
            ))
    return rows

@router.post("/")
def upsert_device(body: DeviceUpsert, request: Request):
    engine = request.app.state.engine
    detector = request.app.state.detector
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
        d.last_seen_at = datetime.utcnow()
        s.add(d)
        s.commit()
    detector.set_overrides(body.device_id, body.idle_threshold_w, body.idle_duration_sec)
    return {"ok": True}

class DeviceConfigPatch(BaseModel):
    idle_threshold_w: Optional[float] = None
    idle_duration_sec: Optional[int] = None

@router.patch("/{device_id}/config")
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
        detector.set_overrides(device_id, d.idle_threshold_w, d.idle_duration_sec)
        return {"ok": True}

class CommandBody(BaseModel):
    action: str  # "on" | "off"

@router.post("/{device_id}/command")
def device_command(device_id: str, body: CommandBody, request: Request):
    engine = request.app.state.engine
    publish = request.app.state.publish_switch
    with Session(engine) as s:
        d = s.exec(select(Device).where(Device.device_id == device_id)).first()
        if not d:
            raise HTTPException(status_code=404, detail="device not found")
        if not d.switch_id:
            raise HTTPException(status_code=400, detail="device has no switch mapping")
        state = "ON" if body.action.lower() == "on" else "OFF"
        publish(d.switch_id, state, d.switch_channel)
        return {"ok": True, "published": {"switch_id": d.switch_id, "channel": d.switch_channel, "state": state}}
