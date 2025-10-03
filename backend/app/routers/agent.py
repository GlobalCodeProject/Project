# app/routers/agent.py
from fastapi import APIRouter, Request
from datetime import datetime

router = APIRouter()

@router.post("/agent/telemetry/dc/{device_id}")
def agent_dc(device_id: str, body: dict, request: Request):
    """HTTP DC ingest compatible with your MQTT handlers."""
    # shape payload to match the MQTT handler expectations
    payload = {
        "v": body.get("v"),
        "i": body.get("i"),
        "p": body.get("p"),
        "ts": body.get("ts") or datetime.utcnow().isoformat(),
    }
    request.app.state.handle_dc(device_id, payload)
    return {"ok": True}

@router.post("/agent/telemetry/ac/{device_id}")
def agent_ac(device_id: str, body: dict, request: Request):
    payload = {
        "v": body.get("v"),
        "i": body.get("i"),
        "p": body.get("p"),
        "pf": body.get("pf"),
        "f": body.get("f"),
        "e_wh": body.get("e_wh"),
        "ts": body.get("ts") or datetime.utcnow().isoformat(),
    }
    request.app.state.handle_ac(device_id, payload)
    return {"ok": True}
