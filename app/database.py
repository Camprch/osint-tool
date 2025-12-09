# app/database.py
from contextlib import contextmanager
from pathlib import Path

from sqlmodel import SQLModel, create_engine, Session

DB_PATH = Path("data/osint.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    # importe les modèles pour que SQLModel voie les tables
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
