from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_env: str = "dev"
    api_port: int = 8000

    # --- MQTT (HiveMQ Cloud) ---
    mqtt_host: str = "7d1417b4c08544b99cab7d8f73fc591c.s1.eu.hivemq.cloud"
    mqtt_port: int = 8883
    mqtt_base: str = "spo/v1"

    # NEW: auth + transport
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_tls: bool = True
    mqtt_ws: bool = False
    mqtt_ws_path: str = "/mqtt"

    # NEW: keepalive + client id (these caused the pydantic error)
    mqtt_keepalive: int = 60
    mqtt_client_id: Optional[str] = "spo-backend-raspi4b-1"

    # --- Idle detection defaults ---
    idle_power_threshold_w: float = 10.0
    idle_duration_sec: int = 300

    # --- DB ---
    db_url: str = "sqlite:///./data/app.db"

    # --- Reporting (optional) ---
    tariff_usd_per_kwh: float = 0.20
    co2_kg_per_kwh: float = 0.40

    # load from .env
    model_config = {"env_file": ".env"}

@lru_cache
def get_settings() -> Settings:
    return Settings()
