from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GenerationSection(str, Enum):
    OVERVIEW = "overview"
    KEY_IDEAS = "key_ideas"
    CHAPTER_SUMMARY = "chapter_summary"
    CRITIQUE = "critique"
    QUIZ = "quiz"


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
            "model",
            "prompt_version",
            "schema_version",
            name="uq_book_generation",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    book_id: str = Field(foreign_key="books.id", index=True)
    section: GenerationSection = Field(
        sa_column=Column(
            SAEnum(
                GenerationSection,
                values_callable=lambda enum_class: [member.value for member in enum_class],
                native_enum=False,
            ),
            nullable=False,
        )
    )
    content_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    provider: str
    model: str
    prompt_version: str
    schema_version: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now, sa_column_kwargs={"onupdate": utc_now})
