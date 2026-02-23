import os

from sqlmodel import SQLModel, create_engine


database_url = os.getenv("DATABASE_URL", "sqlite:///./bookwise.db")
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
