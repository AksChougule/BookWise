from __future__ import annotations

from fastapi import APIRouter

from app.observability.metrics import snapshot


router = APIRouter()


@router.get("/metrics")
def get_metrics() -> dict[str, object]:
    return snapshot()
