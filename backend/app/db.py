# backend/app/db.py
import os
from sqlmodel import SQLModel, create_engine
from .config import get_settings

settings = get_settings()
db_url = settings.resolved_db_url

# Create ./data only for local sqlite path
if db_url.startswith("sqlite:///./"):
    os.makedirs("./data", exist_ok=True)

engine = create_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,  # good hygiene on Postgres
)

def init_db(reset: bool = False):
    from . import models  # import models before touching metadata
    # Only auto-drop for local SQLite if explicitly asked
    if reset and db_url.startswith("sqlite"):
        SQLModel.metadata.drop_all(engine)
        print("[DB] Dropped all tables for clean reset.")
    SQLModel.metadata.create_all(engine)
    print("[DB] Created/ensured all tables.")
