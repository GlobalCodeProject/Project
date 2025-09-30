from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter()

# In-memory MVP store, will be swapped for DB later
_alerts: List[dict] = []  # each: {"id": int, "device_id": str, "status": "open", ...}
_next_id = 1

def _add_alert(alert: dict):
    global _next_id
    alert["id"] = _next_id
    _next_id += 1
    _alerts.append(alert)

@router.get("/")
def list_alerts(status: str = "open"):
    return [a for a in _alerts if a.get("status") == status]

class AckBody(BaseModel):
    id: int

@router.post("/ack")
def ack_alert(b: AckBody):
    for a in _alerts:
        if a["id"] == b.id and a["status"] == "open":
            a["status"] = "ack"
            return {"ok": True, "alert": a}
    return {"ok": False, "msg": "not found or not open"}
