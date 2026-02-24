from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: Literal["openai"] = Field(default="openai")
    model: Literal["gpt-5-mini"] = Field(default="gpt-5-mini")
    temperature: float | None = Field(default=None)
    max_output_tokens: int | None = Field(default=1200)
    timeout_seconds: int = Field(default=45)


class AppConfig(BaseModel):
    llm: LLMConfig


def _config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "llm.yml"


def _env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _load_yaml_config() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return {}

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw
    return {}


def get_app_config() -> AppConfig:
    load_dotenv(_env_path(), override=False)

    raw = _load_yaml_config()
    llm = LLMConfig(**raw)

    env_temperature = os.getenv("LLM_TEMPERATURE")
    env_max_output_tokens = os.getenv("LLM_MAX_OUTPUT_TOKENS")
    env_timeout_seconds = os.getenv("LLM_TIMEOUT_SECONDS")

    if env_temperature is not None:
        llm.temperature = float(env_temperature)
    if env_max_output_tokens is not None:
        llm.max_output_tokens = int(env_max_output_tokens)
    if env_timeout_seconds is not None:
        llm.timeout_seconds = int(env_timeout_seconds)

    return AppConfig(llm=llm)
