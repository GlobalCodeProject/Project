from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# This callable is injected from app.main → mqtt.publish_switch
_publish = None

class ApproveBody(BaseModel):
    channel_id: str
    action: str  # "shutdown" -> OFF, anything else -> ON

@router.post("/approve")
def approve(b: ApproveBody):
    state = "OFF" if b.action.lower() == "shutdown" else "ON"
    if _publish:
        _publish(b.channel_id, state)
    return {"ok": True, "state": state}
