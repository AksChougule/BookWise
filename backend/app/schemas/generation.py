from __future__ import annotations

from pydantic import BaseModel, Field


class OverviewOut(BaseModel):
    overview: str = Field(min_length=20)
    reading_time_minutes: int = Field(ge=1, le=240)


class KeyIdeasOut(BaseModel):
    key_ideas: list[str] = Field(min_length=3, max_length=10)


class ChapterItem(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=10)


class ChaptersOut(BaseModel):
    chapters: list[ChapterItem] = Field(min_length=5, max_length=25)


class CritiqueOut(BaseModel):
    strengths: list[str] = Field(min_length=2, max_length=8)
    weaknesses: list[str] = Field(min_length=2, max_length=8)
    who_should_read: list[str] = Field(min_length=2, max_length=8)
