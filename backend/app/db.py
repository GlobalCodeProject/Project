import os
from sqlmodel import SQLModel, create_engine
from .config import get_settings

settings = get_settings()

# Ensure ./data directory exists if using the default SQLite path
if settings.db_url.startswith("sqlite:///./"):
    os.makedirs("./data", exist_ok=True)

engine = create_engine(settings.db_url, echo=False)


def init_db():
    """Create tables on startup (MVP)."""
    from . import models  # ensure models are imported before create_all
    SQLModel.metadata.create_all(engine)
