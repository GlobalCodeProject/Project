# backend/app/main.py
from fastapi import FastAPI
from datetime import datetime
from sqlmodel import Session, select
import threading
from .config import get_settings
from .db import init_db, engine
from .models import Device, TelemetryDC, TelemetryAC, Alert
from .services.mailer import Mailer
from .services.mqtt_bridge import MQTTBridge
from .services.idle_detector import IdleDetector
from .services.rolling_stats import RollingStats
from .routers import health, devices, telementry, ac_telemetry, alerts, reports, debug, agent
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Smart Power Optimizer (Backend)")
# Add this RIGHT AFTER creating the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins during development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)
settings = get_settings()
mailer = Mailer()


# -------- In-memory stores / services --------
latest_dc = {}  # device_id -> last DC payload
latest_ac = {}  # device_id -> last AC payload
rolling = RollingStats()
detector = IdleDetector(
    default_threshold_w=settings.idle_power_threshold_w,
    default_duration_s=settings.idle_duration_sec,
    window=1,
)

# -------- Helpers --------
def _apply_device_overrides_from_db():
    with Session(engine) as s:
        for d in s.exec(select(Device)).all():
            detector.set_overrides(d.device_id, d.idle_threshold_w, d.idle_duration_sec)

def _raise_alert(device_id: str, power_w: float):
    # Create alert and send an email (fire-and-forget thread)
    with Session(engine) as s:
        th, du = detector._cfg(device_id)
        a = Alert(
            device_id=device_id,
            threshold_w=th,
            duration_s=du,
            status="open",
        )
        s.add(a)
        s.commit()
        s.refresh(a)  # ensure a.id is populated
        d = s.exec(select(Device).where(Device.device_id == device_id)).first()

    def _send_email():
        try:
            mailer.send_alert_created(
                device_id=device_id,
                device_name=d.name if d else device_id,
                power_w=power_w or 0.0,
                threshold_w=th,
                duration_s=du,
                alert_id=a.id,
            )
        except Exception as e:
            print("[MAIL] Error:", e)

    # start the email thread OUTSIDE the function body
    threading.Thread(target=_send_email, daemon=True).start()

def _handle_idle(device_id: str, power_w: float):
    if detector.add(device_id, float(power_w or 0)):
        print(f"[IdleDetector] sustained idle: {device_id} → creating alert if none open")
        with Session(engine) as s:
            existing = s.exec(
                select(Alert).where(
                    Alert.device_id == device_id,
                    Alert.status.in_(("open", "snoozed", "ack")),
                    )
            ).first()
        if not existing:
            _raise_alert(device_id, power_w)

# -------- Ingest callbacks --------
def _on_dc(device_id: str, payload: dict):
    print("DC IN:", device_id, payload)
    latest_dc[device_id] = payload
    v = float(payload.get("v") or 0)
    i = float(payload.get("i") or 0)
    p = float(payload.get("p") or 0)
    ts = datetime.utcnow()
    with Session(engine) as s:
        s.add(TelemetryDC(device_id=device_id, voltage_v=v, current_a=i, power_w=p, ts=ts))
        d = s.exec(select(Device).where(Device.device_id == device_id)).first()
        if d:
            d.last_seen_at = ts
            d.current_power_w = p
            s.add(d)
        s.commit()
    rolling.add(device_id, p)
    _handle_idle(device_id, p)

def _on_ac(device_id: str, payload: dict):
    print("AC IN:", device_id, payload)
    latest_ac[device_id] = payload
    v  = float(payload.get("v") or 0)
    i  = float(payload.get("i") or 0)
    p  = float(payload.get("p") or 0)
    pf = payload.get("pf"); pf = float(pf) if pf is not None else None
    f  = payload.get("f");  f  = float(f)  if f  is not None else None
    e  = payload.get("e_wh"); e = float(e) if e is not None else None
    ts = datetime.utcnow()
    with Session(engine) as s:
        s.add(TelemetryAC(device_id=device_id, voltage_v=v, current_a=i,
                          power_w=p, pf=pf, frequency_hz=f, energy_wh=e, ts=ts))
        d = s.exec(select(Device).where(Device.device_id == device_id)).first()
        if d:
            d.last_seen_at = ts
            d.current_power_w = p
            s.add(d)
        s.commit()
    rolling.add(device_id, p)
    _handle_idle(device_id, p)

# -------- Single MQTT bridge (HiveMQ-ready) --------
mqtt = MQTTBridge(
    host=settings.mqtt_host,
    port=settings.mqtt_port,
    base=settings.mqtt_base,
    on_dc_measure=_on_dc,
    on_ac_measure=_on_ac,
    username=settings.mqtt_username,
    password=settings.mqtt_password,
    use_tls=settings.mqtt_tls,
    use_ws=settings.mqtt_ws,
    ws_path=settings.mqtt_ws_path,
    keepalive=settings.mqtt_keepalive,
    client_id=settings.mqtt_client_id,
)

# -------- Routers --------
app.include_router(health.router, prefix="", tags=["health"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])
app.include_router(telementry.router, prefix="/telemetry", tags=["telemetry-dc"])
app.include_router(ac_telemetry.router, prefix="/telemetry", tags=["telemetry-ac"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(debug.router, prefix="", tags=["debug"])
app.include_router(agent.router, tags=["agent"])

# -------- Shared state injection --------
app.state.engine = engine
app.state.latest_dc = latest_dc
app.state.latest_ac = latest_ac
app.state.rolling = rolling
app.state.detector = detector
app.state.publish_switch = mqtt.publish_switch
app.state.handle_dc = _on_dc
app.state.handle_ac = _on_ac
app.state.mailer = mailer

# -------- Lifecycle --------
@app.on_event("startup")
def _startup():
    init_db(reset=False)
    _apply_device_overrides_from_db()
    if not getattr(app.state, "mqtt_started", False):
        mqtt.start()
        app.state.mqtt_started = True

@app.get("/")
def root():
    return {"name": "spo-backend", "env": settings.app_env}
