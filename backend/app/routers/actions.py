from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from ..models import Approval  

router = APIRouter()

# This callable is injected from app.main → mqtt.publish_switch
publish = None


class ApproveBody(BaseModel):
    channel_id: str
    action: str  # "shutdown" -> OFF, anything else -> ON


class ApprovalRecord(BaseModel):
    id: int
    channel_id: str
    action: str
    state: str
    ts: datetime


@router.post("/approve")
def approve(b: ApproveBody, request: Request):
    """Create an approval record and publish to MQTT."""
    engine = request.app.state.engine
    state = "OFF" if b.action.lower() == "shutdown" else "ON"

    # Persist to database
    with Session(engine) as s:
        approval = Approval(
            channel_id=b.channel_id,
            action=b.action,
            state=state,
            ts=datetime.utcnow()
        )
        s.add(approval)
        s.commit()
        s.refresh(approval)  # Get the auto-generated ID
        approval_id = approval.id

    # Publish to MQTT
    if publish:
        publish(b.channel_id, state)

    return {
        "ok": True,
        "id": approval_id,
        "state": state,
        "ts": approval.ts
    }


@router.get("/approve/history/{channel_id}", response_model=List[ApprovalRecord])
def get_approval_history(channel_id: str, request: Request, limit: int = 50):
    """Get approval history for a specific channel from the database."""
    engine = request.app.state.engine

    with Session(engine) as s:
        approvals = s.exec(
            select(Approval)
            .where(Approval.channel_id == channel_id)
            .order_by(Approval.ts.desc())
            .limit(limit)
        ).all()

    return [
        ApprovalRecord(
            id=a.id,
            channel_id=a.channel_id,
            action=a.action,
            state=a.state,
            ts=a.ts
        )
        for a in approvals
    ]


@router.get("/approve/history", response_model=List[ApprovalRecord])
def get_all_approval_history(request: Request, limit: int = 100):
    """Get all approval history from the database."""
    engine = request.app.state.engine

    with Session(engine) as s:
        approvals = s.exec(
            select(Approval)
            .order_by(Approval.ts.desc())
            .limit(limit)
        ).all()

    return [
        ApprovalRecord(
            id=a.id,
            channel_id=a.channel_id,
            action=a.action,
            state=a.state,
            ts=a.ts
        )
        for a in approvals
    ]