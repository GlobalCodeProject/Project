from fastapi import FastAPI
from datetime import datetime
from sqlmodel import Session
from .config import get_settings
from .db import init_db, engine
from .models import TelemetryDC, Alert
from .services.mqtt_bridge import MQTTBridge
from .services.idle_detector import IdleDetector
from .routers import health, devices, telementry, alerts, actions

app = FastAPI(title="Smart Power Optimizer (Backend)")
settings = get_settings()

# in-memory stores 
latest_dc = {}   # device_id -> last payload
alerts_store = alerts  # import alias
telementry._latest_dc = latest_dc

# Idle detector
detector = IdleDetector(
    threshold_w=settings.idle_power_threshold_w,
    duration_s=settings.idle_duration_sec,
    window=5,
)

def _raise_alert(device_id: str):
    # In-memory alert record (MVP); also persist to DB for history
    alert = {
        "device_id": device_id,
        "reason": "idle_detected",
        "threshold_w": settings.idle_power_threshold_w,
        "duration_s": settings.idle_duration_sec,
        "status": "open",
        "ts_open": datetime.utcnow().isoformat()
    }
    alerts_store._add_alert(alert)
    # Persist
    with Session(engine) as s:
        s.add(Alert(
            device_id=device_id,
            threshold_w=settings.idle_power_threshold_w,
            duration_s=settings.idle_duration_sec,
            status="open",
        ))
        s.commit()

def _on_dc(device_id: str, payload: dict):
    # Update cache
    latest_dc[device_id] = payload

    # Persist telemetry
    try:
        v = float(payload.get("v", 0))
        i = float(payload.get("i", 0))
        p = float(payload.get("p", 0))
    except Exception:
        v = i = p = 0.0
    with Session(engine) as s:
        s.add(TelemetryDC(device_id=device_id, voltage_v=v, current_a=i, power_w=p))
        s.commit()

    # Idle detection
    if detector.add(device_id, p):
        # Only raise if not already open for this device
        open_for_device = [a for a in alerts_store._alerts
                           if a["device_id"] == device_id and a["status"] == "open"]
        if not open_for_device:
            _raise_alert(device_id)

# MQTT bridge
mqtt = MQTTBridge(settings.mqtt_host, settings.mqtt_port, settings.mqtt_base, _on_dc)

# --- Mount routers ---
app.include_router(health.router, prefix="", tags=["health"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])
app.include_router(telementry.router, prefix="/telemetry", tags=["telemetry"])  # name as in your tree
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(actions.router, prefix="/actions", tags=["actions"])

# Inject shared MVP objects
telementry._latest_dc = latest_dc
actions._publish = mqtt.publish_switch

@app.on_event("startup")
def _startup():
    init_db()
    mqtt.start()

@app.get("/")
def root():
    return {"name": "spo-backend", "env": settings.app_env}
