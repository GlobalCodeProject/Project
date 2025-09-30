from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
_devices = {}  # device_id -> {"name":..., "kind":...}

class UpsertDevice(BaseModel):
    device_id: str
    name: str = "Unnamed"
    kind: str = "dc_sensor"  # "dc_sensor" | "ac_sensor" | "switch"

@router.get("/")
def list_devices():
    return [{"device_id": k, **v} for k, v in _devices.items()]

@router.post("/")
def upsert_device(d: UpsertDevice):
    _devices[d.device_id] = {"name": d.name, "kind": d.kind}
    return {"ok": True}
