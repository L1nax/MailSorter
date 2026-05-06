from __future__ import annotations
import os
from sqlmodel import SQLModel, Session, create_engine

DATA_DIR = os.environ.get("MAILSORT_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "mailsort.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
