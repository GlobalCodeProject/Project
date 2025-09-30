# backend/app/routers/ac_telemetry.py
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from ..models import TelemetryAC

router = APIRouter()

class ACLastReading(BaseModel):
    v: Optional[float] = None
    i: Optional[float] = None
    p: Optional[float] = None
    pf: Optional[float] = None
    f: Optional[float] = None
    e_wh: Optional[float] = None
    ts: Optional[datetime] = None

@router.get("/ac/{device_id}", response_model=ACLastReading)
def last_ac(device_id: str, request: Request):
    """Return the most recent AC reading from the database."""
    engine = request.app.state.engine
    with Session(engine) as s:
        row = s.exec(
            select(TelemetryAC)
            .where(TelemetryAC.device_id == device_id)
            .order_by(TelemetryAC.ts.desc())
            .limit(1)
        ).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"No data for device '{device_id}'")
    return {
        "v": row.voltage_v,
        "i": row.current_a,
        "p": row.power_w,
        "pf": row.pf,
        "f": row.frequency_hz,
        "e_wh": row.energy_wh,
        "ts": row.ts,
    }
