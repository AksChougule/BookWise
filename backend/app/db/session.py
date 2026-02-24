import os
import logging

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine


database_url = os.getenv("DATABASE_URL", "sqlite:///./bookwise.db")
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, echo=False, connect_args=connect_args)
logger = logging.getLogger(__name__)


def _ensure_book_generations_columns() -> None:
    if not database_url.startswith("sqlite"):
        return

    with engine.begin() as connection:
        table_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='book_generations'")
        ).first()
        if table_exists is None:
            return

        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info('book_generations')")).fetchall()
        }

        alter_statements: list[str] = []
        if "status" not in columns:
            alter_statements.append(
                "ALTER TABLE book_generations ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
            )
        if "started_at" not in columns:
            alter_statements.append("ALTER TABLE book_generations ADD COLUMN started_at TIMESTAMP")
        if "finished_at" not in columns:
            alter_statements.append("ALTER TABLE book_generations ADD COLUMN finished_at TIMESTAMP")
        if "error_code" not in columns:
            alter_statements.append("ALTER TABLE book_generations ADD COLUMN error_code TEXT")
        if "error_message" not in columns:
            alter_statements.append("ALTER TABLE book_generations ADD COLUMN error_message TEXT")
        if "attempt_count" not in columns:
            alter_statements.append(
                "ALTER TABLE book_generations ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
            )

        for statement in alter_statements:
            connection.execute(text(statement))

        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_book_generations_book_id ON book_generations (book_id)")
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_book_generations_status ON book_generations (status)")
        )
        try:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_book_generation_cache_key "
                    "ON book_generations (book_id, section, prompt_version, provider, model)"
                )
            )
        except Exception:
            logger.exception("Unable to create unique cache key index for book_generations")


def init_db() -> None:
    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _ensure_book_generations_columns()
