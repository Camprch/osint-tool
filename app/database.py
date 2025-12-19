# app/database.py
from contextlib import contextmanager
from pathlib import Path
import os


from sqlmodel import SQLModel, create_engine, Session

# Nouvelle logique :
# 1. Si pas de db locale -> on regarde DB_URL
# 2. Si pas de DB_URL -> on crée une db locale

DB_PATH = Path("data/osint.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

db_url = os.getenv("DB_URL")
if db_url:
    # Ajoute sslmode=require si PostgreSQL et pas déjà présent
    if db_url.startswith("postgres") and "sslmode" not in db_url:
        sep = '&' if '?' in db_url else '?'
        db_url = f"{db_url}{sep}sslmode=require"
    DATABASE_URL = db_url
    print(f"[DEBUG] DATABASE_URL utilisé : {DATABASE_URL}")
    is_sqlite = DATABASE_URL.startswith("sqlite")
else:
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




from typing import Generator

@contextmanager
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


# Dépendance FastAPI
def get_db():
    with Session(engine) as session:
        yield session
