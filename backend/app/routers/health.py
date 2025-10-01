from time import time

from fastapi import APIRouter, Request
from sqlmodel import Session

router = APIRouter()

@router.get("/health")
def health(request: Request):
    # DB ping
    try:
        with Session(request.app.state.engine) as s:
            s.exec("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return {"ok": True, "db": db_ok}

@router.post("/__test_email")
def test_email(request: Request):
    m = getattr(request.app.state, "mailer", None)
    if not m:
        return {"ok": False, "msg": "mailer not set"}
    m._send("SPO test email", "<p>This is a test</p>")
    return {"ok": True}


@router.get("/debug/idle/{device_id}")
def idle_debug(device_id: str, request: Request):
    det = request.app.state.detector
    buf = list(det.buffers.get(device_id, []))
    th, du = det._cfg(device_id)
    below_since = det.below_since.get(device_id)
    now = time()
    return {
        "device": device_id,
        "threshold_w": th,
        "duration_s": du,
        "window": det.window,
        "samples": buf,
        "avg_w": (sum(buf)/len(buf) if buf else None),
        "below_since": below_since,
        "elapsed_s": (now - below_since) if below_since else 0,
    }

