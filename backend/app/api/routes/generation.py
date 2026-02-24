from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.middleware.rate_limit import limiter
from app.observability.logging import get_logger
from app.observability.metrics import increment, observe_ms
from app.services.generation_service import (
    GenerationInProgressError,
    GenerationInvalidSectionError,
    GenerationNotFoundError,
    GenerationOutputValidationError,
    GenerationPreviouslyFailedError,
    GenerationUpstreamError,
    generate_section,
)


router = APIRouter()
logger = get_logger(__name__)


@router.post("/books/{work_id}/generate/{section}")
@limiter.limit("30/minute")
async def generate_book_section(
    request: Request,
    work_id: str,
    section: str,
    force: bool = Query(default=False),
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None)
    cache_key = f"{work_id}:{section}"
    start = time.perf_counter()
    increment("generation.request", labels={"section": section})
    logger.info(
        "generation.request.start",
        extra={
            "request_id": request_id,
            "method": "POST",
            "path": f"/api/books/{work_id}/generate/{section}",
            "work_id": work_id,
            "section": section,
            "force": force,
            "cache_key": cache_key,
        },
    )
    try:
        response = await generate_section(
            book_id=work_id,
            section=section,
            force=force,
            request_id=request_id,
        )
        observe_ms("generation.total_ms", (time.perf_counter() - start) * 1000.0, labels={"section": section})
        return response
    except GenerationInProgressError as exc:
        observe_ms("generation.total_ms", (time.perf_counter() - start) * 1000.0, labels={"section": section})
        increment("generation.status.pending", labels={"section": section, "status": "pending"})
        return JSONResponse(
            status_code=202,
            content={
                "stored": False,
                "in_progress": True,
                "retry_after_ms": exc.retry_after_ms,
                "cache_key": {
                    "book_id": work_id,
                    "section": section,
                },
            },
        )
    except GenerationPreviouslyFailedError as exc:
        observe_ms("generation.total_ms", (time.perf_counter() - start) * 1000.0, labels={"section": section})
        increment("generation.status.failed", labels={"section": section, "status": "failed"})
        raise HTTPException(
            status_code=502,
            detail={
                "detail": "Generation previously failed",
                "status": "failed",
                "error_code": exc.error_code,
            },
        )
    except GenerationNotFoundError:
        observe_ms("generation.total_ms", (time.perf_counter() - start) * 1000.0, labels={"section": section})
        raise HTTPException(status_code=404, detail="Book not found")
    except GenerationInvalidSectionError:
        observe_ms("generation.total_ms", (time.perf_counter() - start) * 1000.0, labels={"section": section})
        raise HTTPException(status_code=422, detail="Invalid section")
    except GenerationOutputValidationError:
        observe_ms("generation.total_ms", (time.perf_counter() - start) * 1000.0, labels={"section": section})
        raise HTTPException(status_code=422, detail="Invalid generated content")
    except GenerationUpstreamError:
        observe_ms("generation.total_ms", (time.perf_counter() - start) * 1000.0, labels={"section": section})
        raise HTTPException(status_code=502, detail="OpenAI generation failed")
