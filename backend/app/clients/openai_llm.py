from __future__ import annotations

import json
import os
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import (
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    BadRequestError,
)

from app.llm.schema_utils import enforce_no_additional_properties

logger = logging.getLogger(__name__)


class OpenAILLMClientError(Exception):
    pass


class OpenAILLMClientTransportError(OpenAILLMClientError):
    pass


class OpenAILLMClientOutputError(OpenAILLMClientError):
    pass


class OpenAILLMClient:
    def __init__(self, timeout_seconds: int | None = None) -> None:
        env_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(env_path, override=False)
        api_key = os.getenv("OPENAI_API_KEY")
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)

    async def generate_structured(
        self,
        *,
        model: str,
        prompt: str,
        json_schema: dict[str, Any],
        temperature: float | None,
        max_output_tokens: int | None,
        request_id: str | None = None,
        cache_key: str | None = None,
    ) -> dict[str, Any]:
        strict_schema = enforce_no_additional_properties(json_schema)
        request_kwargs: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "bookwise_generation",
                    "schema": strict_schema,
                    "strict": True,
                }
            },
        }
        if temperature is not None:
            request_kwargs["temperature"] = temperature
        if max_output_tokens is not None:
            request_kwargs["max_output_tokens"] = max_output_tokens

        try:
            response = await self._client.responses.create(**request_kwargs)
        except BadRequestError as exc:
            # This prints the *real* reason for 400 (usually schema/param issue)
            logger.error("OpenAI 400 error body: %s", getattr(exc, "body", None))
            logger.exception(
                "OpenAI call failed during generation (400)",
                extra={
                    "request_id": request_id,
                    "cache_key": cache_key,
                    "error_code": "openai_error",
                },
            )
            raise OpenAILLMClientTransportError("OpenAI request was invalid (400)") from exc
        except APITimeoutError as exc:
            logger.exception(
                "OpenAI call timed out during generation",
                extra={
                    "request_id": request_id,
                    "cache_key": cache_key,
                    "error_code": "timeout",
                },
            )
            raise OpenAILLMClientTransportError("OpenAI request timed out") from exc
        except APIStatusError as exc:
            # Handles 401/403/429/5xx etc.
            logger.error("OpenAI status error body: %s", getattr(exc, "body", None))
            logger.exception(
                "OpenAI status error during generation",
                extra={
                    "request_id": request_id,
                    "cache_key": cache_key,
                    "error_code": "openai_error",
                },
            )
            raise OpenAILLMClientTransportError("OpenAI request failed") from exc
        except APIError as exc:
            logger.exception(
                "OpenAI APIError during generation",
                extra={
                    "request_id": request_id,
                    "cache_key": cache_key,
                    "error_code": "openai_error",
                },
            )
            raise OpenAILLMClientTransportError("OpenAI request failed") from exc

        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise OpenAILLMClientOutputError("OpenAI returned empty output")

        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise OpenAILLMClientOutputError("OpenAI returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise OpenAILLMClientOutputError("OpenAI returned invalid payload")
        return parsed
