# backend/app/routers/telementry.py
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from ..models import TelemetryDC

router = APIRouter()

class DCLastReading(BaseModel):
    v: Optional[float] = None
    i: Optional[float] = None
    p: Optional[float] = None
    ts: Optional[datetime] = None

@router.get("/dc/{device_id}", response_model=DCLastReading)
def last_dc(device_id: str, request: Request):
    print("device ID: ", device_id)
    """Return the most recent DC reading from the database."""
    engine = request.app.state.engine
    with Session(engine) as s:
        row = s.exec(
            select(TelemetryDC)
            .where(TelemetryDC.device_id == device_id)
            .order_by(TelemetryDC.ts.desc())
            .limit(1)
        ).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"No data for device '{device_id}'")
    return {"v": row.voltage_v, "i": row.current_a, "p": row.power_w, "ts": row.ts}

# HTTP ingest (fallback path for tests / non-MQTT devices)
class HttpTelemetryIn(BaseModel):
    deviceId: str
    kind: str  # "dc" or "ac"
    timestamp: Optional[datetime] = None
    power_w: float
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    pf: Optional[float] = None
    frequency_hz: Optional[float] = None
    energy_wh: Optional[float] = None

@router.post("")   # accept /telemetry 
@router.post("/")  # and /telemetry/ 
def http_ingest(body: HttpTelemetryIn, request: Request):
    """
    Accept telemetry via HTTP and route through the same handlers used by MQTT,
    so idle detection, stats, and persistence all apply.
    """
    if body.kind not in ("dc", "ac"):
        raise HTTPException(status_code=400, detail="kind must be 'dc' or 'ac'")

    # Build the normalized payload expected by the ingest callbacks
    ts = (body.timestamp or datetime.utcnow()).isoformat()
    payload = {"v": body.voltage_v, "i": body.current_a, "p": body.power_w, "ts": ts}

    if body.kind == "dc":
        request.app.state.handle_dc(body.deviceId, payload)
    else:
        payload.update({"pf": body.pf, "f": body.frequency_hz, "e_wh": body.energy_wh})
        request.app.state.handle_ac(body.deviceId, payload)

    return {"ok": True}
