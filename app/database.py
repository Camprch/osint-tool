# app/database.py
from contextlib import contextmanager
from pathlib import Path
import os

from sqlmodel import SQLModel, create_engine, Session

# 1) On essaie de lire la chaîne de connexion depuis l'environnement
#    On supporte d'abord DATABASE_URL, puis DB_URL (ton .env actuel)
env_db_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

if env_db_url:
    # Prod / CI : Neon, Render, etc.
    DATABASE_URL = env_db_url
    is_sqlite = DATABASE_URL.startswith("sqlite")
else:
    # Dev local : fallback sur ton SQLite comme avant
    DB_PATH = Path("data/osint.db")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    is_sqlite = True

# 2) Création de l'engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    # check_same_thread uniquement pour SQLite
    connect_args={"check_same_thread": False} if is_sqlite else {},
)


def init_db() -> None:
    # importe les modèles pour que SQLModel connaisse les tables
    from app.models.message import Message  # noqa: F401
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Session:
    with Session(engine) as session:
        yield session


# Dépendance FastAPI
def get_db():
    with Session(engine) as session:
        yield session
