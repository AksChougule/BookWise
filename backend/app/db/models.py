from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Book(SQLModel, table=True):
    __tablename__ = "books"

    id: str = Field(primary_key=True)
    title: str
    authors: str
    first_publish_year: int | None = Field(default=None)
    cover_url: str | None = Field(default=None)
    openlibrary_url: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now, sa_column_kwargs={"onupdate": utc_now})


class BookGeneration(SQLModel, table=True):
    __tablename__ = "book_generations"
    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "section",
            "provider",
            "model",
            "prompt_version",
            name="uq_book_generation",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    book_id: str = Field(foreign_key="books.id", index=True)
    section: str = Field(index=True)
    status: str = Field(default="pending", index=True)
    content_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    provider: str
    model: str
    prompt_version: str
    schema_version: str
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    error_code: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    attempt_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now, sa_column_kwargs={"onupdate": utc_now})
