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


def _safe_output_preview(output_text: str | None, max_chars: int = 500) -> tuple[str, int]:
    normalized = (output_text or "").strip()
    return normalized[:max_chars], len(normalized)


def _extract_work_context(cache_key: str | None) -> tuple[str | None, str | None]:
    if not cache_key:
        return None, None
    parts = cache_key.split(":")
    if len(parts) < 2:
        return None, None
    return parts[0], parts[1]


def _coerce_text(maybe: Any) -> str | None:
    if isinstance(maybe, str):
        return maybe
    value = getattr(maybe, "value", None)
    if isinstance(value, str):
        return value
    if isinstance(maybe, dict):
        direct = maybe.get("text")
        if isinstance(direct, str):
            return direct
        if isinstance(direct, dict):
            nested_value = direct.get("value")
            if isinstance(nested_value, str):
                return nested_value
    return None


def _coerce_json(maybe: Any) -> dict[str, Any] | list[Any] | None:
    if isinstance(maybe, (dict, list)):
        return maybe

    for attr in ("value", "data", "json"):
        value = getattr(maybe, attr, None)
        if isinstance(value, (dict, list)):
            return value

    if isinstance(maybe, dict):
        for key in ("json", "data", "value"):
            nested = maybe.get(key)
            if isinstance(nested, (dict, list)):
                return nested

    return None


def _extract_first_output_json(response: Any) -> dict[str, Any] | list[Any] | None:
    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return None

    for item in output:
        content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
        if not isinstance(content, list):
            continue
        for chunk in content:
            chunk_type = chunk.get("type") if isinstance(chunk, dict) else getattr(chunk, "type", None)
            if chunk_type not in {"output_json", "json", "json_schema"}:
                continue

            if isinstance(chunk, dict):
                candidates = [chunk.get("json"), chunk.get("data"), chunk.get("value"), chunk]
            else:
                candidates = [getattr(chunk, "json", None), getattr(chunk, "data", None), getattr(chunk, "value", None), chunk]

            for candidate in candidates:
                coerced = _coerce_json(candidate)
                if coerced is not None:
                    return coerced

    return None


def _extract_first_output_text(response: Any) -> str | None:
    output = getattr(response, "output", None)
    if isinstance(output, list):
        for item in output:
            content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
            if not isinstance(content, list):
                continue
            for chunk in content:
                chunk_type = chunk.get("type") if isinstance(chunk, dict) else getattr(chunk, "type", None)
                chunk_raw_text = chunk.get("text") if isinstance(chunk, dict) else getattr(chunk, "text", None)
                chunk_text = _coerce_text(chunk_raw_text)
                if chunk_type in {"output_text", "text"} and isinstance(chunk_text, str):
                    normalized = chunk_text.strip()
                    if normalized:
                        return normalized

    fallback = _coerce_text(getattr(response, "output_text", None))
    if isinstance(fallback, str):
        normalized = fallback.strip()
        if normalized:
            return normalized
    return None


def _summarize_response_shape(response: Any) -> dict[str, Any]:
    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return {
            "has_output": bool(output),
            "output_items": 0,
            "output_item_types": [],
            "output_content_types": [],
        }

    output_item_types: list[str | None] = []
    output_content_types: list[list[str | None]] = []
    for item in output:
        item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
        output_item_types.append(str(item_type) if item_type is not None else None)

        content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
        content_types: list[str | None] = []
        if isinstance(content, list):
            for chunk in content:
                chunk_type = chunk.get("type") if isinstance(chunk, dict) else getattr(chunk, "type", None)
                content_types.append(str(chunk_type) if chunk_type is not None else None)
        output_content_types.append(content_types)

    return {
        "has_output": True,
        "output_items": len(output),
        "output_item_types": output_item_types,
        "output_content_types": output_content_types,
    }


def _extract_finish_reason(response: Any) -> str | None:
    output = getattr(response, "output", None)
    if not output or not isinstance(output, list):
        return None
    first_item = output[0]
    if isinstance(first_item, dict):
        value = first_item.get("finish_reason")
    else:
        value = getattr(first_item, "finish_reason", None)
    return str(value) if value is not None else None


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

        json_obj = _extract_first_output_json(response)
        if json_obj is not None:
            if isinstance(json_obj, dict):
                return json_obj
            raise OpenAILLMClientOutputError("OpenAI returned invalid payload")

        output_text = _extract_first_output_text(response)
        if not output_text:
            work_id, section = _extract_work_context(cache_key)
            shape = _summarize_response_shape(response)
            logger.error(
                "OpenAI returned empty output",
                extra={
                    "request_id": request_id,
                    "cache_key": cache_key,
                    "work_id": work_id,
                    "section": section,
                    "error_code": "empty_output",
                    **shape,
                },
            )
            raise OpenAILLMClientOutputError("OpenAI returned empty output")
        finish_reason = _extract_finish_reason(response)

        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            work_id, section = _extract_work_context(cache_key)
            shape = _summarize_response_shape(response)
            _, output_length = _safe_output_preview(output_text)
            output_tail = output_text[-200:] if output_text else None
            logger.exception(
                "OpenAI output validation failed",
                extra={
                    "request_id": request_id,
                    "section": section,
                    "work_id": work_id,
                    "error_code": "schema_validation",
                    "finish_reason": finish_reason,
                    "output_tail": output_tail,
                    "output_length": output_length,
                    **shape,
                },
            )
            raise OpenAILLMClientOutputError("OpenAI returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise OpenAILLMClientOutputError("OpenAI returned invalid payload")
        return parsed
