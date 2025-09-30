from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    api_port: int = 8000

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_base: str = "spo/v1"

    idle_power_threshold_w: float = 10.0
    idle_duration_sec: int = 300

    db_url: str = "sqlite:///./data/app.db"

    model_config = {
        "env_file": ".env"  # load from .env if present
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
