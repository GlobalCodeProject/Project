from fastapi import APIRouter

router = APIRouter()

# This dict is injected from app.main on startup
_latest_dc = {}  # device_id -> {"v":..., "i":..., "p":..., "ts":...}

@router.get("/dc/{device_id}")
def last_dc(device_id: str):
    return _latest_dc.get(device_id, {"msg": "no data"})
