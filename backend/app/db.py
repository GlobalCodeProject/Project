# backend/app/db.py
import os
from sqlmodel import SQLModel, create_engine
from .config import get_settings

settings = get_settings()

if settings.db_url.startswith("sqlite:///./"):
    os.makedirs("./data", exist_ok=True)

engine = create_engine(settings.db_url, echo=False)

def init_db(reset: bool = False) -> None:
    """
    Initialize DB schema on startup.
    - If reset=True (dev only), drop then recreate tables.
    - Always import models BEFORE touching metadata so tables are registered.
    """
    from . import models  # <- IMPORTANT: register tables on metadata

    if reset:
        SQLModel.metadata.drop_all(engine)
        print("[DB] Dropped all tables (dev reset).")

    SQLModel.metadata.create_all(engine)
    print("[DB] Created/ensured all tables.")
