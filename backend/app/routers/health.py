from time import time

from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/health")
def health():
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

