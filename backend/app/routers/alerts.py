from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select
from ..models import Alert, Device

router = APIRouter()

ALLOWED_FOR_SHUTDOWN = ("open", "ack", "snoozed")

class ShutdownBody(BaseModel):
    reason: Optional[str] = None

@router.post("/{alert_id}/shutdown")
@router.post("/{alert_id}/shutdown/")
def shutdown_alert(alert_id: int, body: ShutdownBody, request: Request):
    engine  = request.app.state.engine
    publish = request.app.state.publish_switch

    with Session(engine) as s:
        a = s.get(Alert, alert_id)
        if not a:
            raise HTTPException(404, "alert not found")

        status     = a.status              # capture while bound
        device_id  = a.device_id           # capture while bound

        if status not in ALLOWED_FOR_SHUTDOWN:
            raise HTTPException(400, f"alert not actionable (status={status})")

        d = s.exec(select(Device).where(Device.device_id == device_id)).first()
        if not d or not d.switch_id:
            raise HTTPException(400, "device has no switch mapping")

        switch_id  = d.switch_id
        channel    = d.switch_channel

        # Publish OFF command
        publish(switch_id, "OFF", channel)

        # Close alert
        a.status   = "closed"
        a.ts_close = datetime.utcnow()
        s.add(a)
        s.commit()

    # Now we return only captured primitives (no detached ORM access)
    return {
        "ok": True,
        "alert_id": alert_id,
        "device_id": device_id,
        "action": "OFF",
        "published": {"switch_id": switch_id, "channel": channel},
        "closed": True,
    }


@router.post("/shutdown-latest")
@router.post("/shutdown-latest/")
def shutdown_latest(request: Request):
    engine  = request.app.state.engine
    publish = request.app.state.publish_switch

    with Session(engine) as s:
        a = s.exec(
            select(Alert)
            .where(Alert.status == "open")
            .order_by(Alert.id.desc())
            .limit(1)
        ).first()
        if not a:
            raise HTTPException(404, "no open alerts")

        alert_id  = a.id
        device_id = a.device_id

        d = s.exec(select(Device).where(Device.device_id == device_id)).first()
        if not d or not d.switch_id:
            raise HTTPException(400, "device has no switch mapping")

        switch_id = d.switch_id
        channel   = d.switch_channel

        publish(switch_id, "OFF", channel)

        a.status   = "closed"
        a.ts_close = datetime.utcnow()
        s.add(a)
        s.commit()

    return {
        "ok": True,
        "alert_id": alert_id,
        "device_id": device_id,
        "action": "OFF",
        "published": {"switch_id": switch_id, "channel": channel},
        "closed": True,
    }
