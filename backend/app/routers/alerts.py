from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from ..models import Alert, Action, Device

router = APIRouter()

class AlertRow(BaseModel):
    id: int
    device_id: str
    status: str
    threshold_w: float
    duration_s: int
    ts_open: datetime
    ts_close: Optional[datetime] = None
    snooze_until: Optional[datetime] = None

class SnoozeBody(BaseModel):
    minutes: int = 10
    reason: Optional[str] = None

class IgnoreBody(BaseModel):
    reason: Optional[str] = None

class ShutdownBody(BaseModel):
    reason: Optional[str] = None

@router.get("/", response_model=List[AlertRow])
def list_alerts(request: Request, status: str = "open", device_id: Optional[str] = None):
    engine = request.app.state.engine
    with Session(engine) as s:
        stmt = select(Alert).where(Alert.status == status)
        if device_id:
            stmt = stmt.where(Alert.device_id == device_id)
        res = s.exec(stmt.order_by(Alert.ts_open.desc())).all()
        return [AlertRow(**a.model_dump()) for a in res]

@router.get("/{alert_id}", response_model=AlertRow)
def get_alert(alert_id: int, request: Request):
    engine = request.app.state.engine
    with Session(engine) as s:
        a = s.get(Alert, alert_id)
        if not a:
            raise HTTPException(status_code=404, detail="alert not found")
        return AlertRow(**a.model_dump())

@router.post("/{alert_id}/ack")
def ack_alert(alert_id: int, request: Request):
    engine = request.app.state.engine
    with Session(engine) as s:
        a = s.get(Alert, alert_id)
        if not a or a.status != "open":
            raise HTTPException(status_code=400, detail="alert not open")
        a.status = "ack"
        s.add(a)
        s.add(Action(alert_id=alert_id, device_id=a.device_id, action="ack"))
        s.commit()
        return {"ok": True}

@router.post("/{alert_id}/snooze")
def snooze_alert(alert_id: int, body: SnoozeBody, request: Request):
    engine = request.app.state.engine
    with Session(engine) as s:
        a = s.get(Alert, alert_id)
        if not a or a.status not in ("open", "ack"):
            raise HTTPException(status_code=400, detail="alert not open/ack")
        a.status = "snoozed"
        a.snooze_until = datetime.utcnow() + timedelta(minutes=body.minutes)
        s.add(a)
        s.add(Action(alert_id=alert_id, device_id=a.device_id, action="snooze", reason=body.reason))
        s.commit()
        return {"ok": True}

@router.post("/{alert_id}/ignore")
def ignore_alert(alert_id: int, body: IgnoreBody, request: Request):
    engine = request.app.state.engine
    with Session(engine) as s:
        a = s.get(Alert, alert_id)
        if not a or a.status not in ("open", "ack", "snoozed"):
            raise HTTPException(status_code=400, detail="alert not actionable")
        a.status = "closed"
        a.ts_close = datetime.utcnow()
        s.add(a)
        s.add(Action(alert_id=alert_id, device_id=a.device_id, action="ignore", reason=body.reason))
        s.commit()
        return {"ok": True}

@router.post("/{alert_id}/shutdown")
def shutdown_alert(alert_id: int, body: ShutdownBody, request: Request):
    engine = request.app.state.engine
    publish = request.app.state.publish_switch

    with Session(engine) as s:
        a = s.get(Alert, alert_id)
        if not a or a.status not in ("open", "ack", "snoozed"):
            raise HTTPException(status_code=400, detail="alert not actionable")

        d = s.exec(select(Device).where(Device.device_id == a.device_id)).first()
        if not d or not d.switch_id:
            raise HTTPException(status_code=400, detail="device not mapped to a switch")

        publish(d.switch_id, "OFF", d.switch_channel)

        a.status = "closed"
        a.ts_close = datetime.utcnow()
        s.add(a)
        s.add(Action(alert_id=alert_id, device_id=a.device_id, action="shutdown", reason=body.reason))
        s.commit()
        return {"ok": True}
