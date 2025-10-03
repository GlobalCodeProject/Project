# backend/app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    api_port: int = 8000

    # MQTT ...
    mqtt_host: str = "d85467e9b3be4d9390f52e2a6c740aa6.s1.eu.hivemq.cloud"
    mqtt_port: int = 8883
    mqtt_base: str = "pow/measure"
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_tls: bool = True
    mqtt_ws: bool = False
    mqtt_ws_path: str = "/mqtt"
    mqtt_keepalive: int = 60
    mqtt_client_id: str = "spo-backend-raspi4b-1"

    # DB (default local SQLite)
    db_url: str = "sqlite:///./data/app.db"

    # Email / SMTP ...
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    smtp_starttls: bool = True
    smtp_from: str = "Smart Power Optimizer <no-reply@example.com>"
    smtp_to: Optional[str] = None
    smtp_use_ssl: bool = False  
    smtp_use_tls: bool = True
    alerts_from: Optional[str] = None
    alerts_to: Optional[str] = None

    idle_power_threshold_w: float = 10.0
    idle_duration_sec: int = 300

    tariff_usd_per_kwh: float = 0.20
    co2_kg_per_kwh: float = 0.40

    @property
    def resolved_db_url(self) -> str:
        """
        Prefer DB_URL; fallback to DATABASE_URL; else use db_url.
        Normalize postgres:// → postgresql+psycopg://.
        Only enforce sslmode=require for non-local hosts.
        Allow override via DB_SSLMODE env.
        """
        raw = (os.getenv("DB_URL") or os.getenv("DATABASE_URL") or self.db_url).strip()

        if raw.startswith("postgres://"):
            raw = raw.replace("postgres://", "postgresql+psycopg://", 1)

        if raw.startswith("postgresql"):
            u = urlparse(raw)
            host = (u.hostname or "").lower()
            qs = dict(parse_qsl(u.query, keep_blank_values=True))

            # If user explicitly set DB_SSLMODE, respect it
            override_sslmode = os.getenv("DB_SSLMODE")

            if override_sslmode:
                qs["sslmode"] = override_sslmode
            else:
                # Only force sslmode=require for non-local hosts
                if "sslmode" not in qs:
                    if host in ("localhost", "127.0.0.1", "::1"):
                        # leave unset (or you can set disable explicitly)
                        pass
                    else:
                        qs["sslmode"] = "require"

            u = u._replace(query=urlencode(qs))
            raw = urlunparse(u)

        return raw

@lru_cache
def get_settings() -> Settings:
    return Settings()
