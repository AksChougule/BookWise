from __future__ import annotations

from threading import Lock
from typing import Any

_ALLOWED_LABELS = {"section", "status", "model"}
_lock = Lock()
_counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}
_timers: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, float]] = {}


def _normalize_labels(labels: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    normalized = []
    for key, value in labels.items():
        if key in _ALLOWED_LABELS and value is not None:
            normalized.append((key, str(value)))
    return tuple(sorted(normalized))


def _render_key(name: str, labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return name
    joined = ",".join(f"{k}={v}" for k, v in labels)
    return f"{name}{{{joined}}}"


def increment(name: str, value: int = 1, labels: dict[str, Any] | None = None) -> None:
    label_key = _normalize_labels(labels)
    with _lock:
        metric_key = (name, label_key)
        _counters[metric_key] = _counters.get(metric_key, 0) + value


def observe_ms(name: str, ms: float, labels: dict[str, Any] | None = None) -> None:
    label_key = _normalize_labels(labels)
    with _lock:
        metric_key = (name, label_key)
        current = _timers.get(metric_key)
        if current is None:
            _timers[metric_key] = {"count": 1.0, "sum": ms, "min": ms, "max": ms}
            return
        current["count"] += 1.0
        current["sum"] += ms
        current["min"] = min(current["min"], ms)
        current["max"] = max(current["max"], ms)


def snapshot() -> dict[str, Any]:
    with _lock:
        counters = {
            _render_key(name, labels): value
            for (name, labels), value in _counters.items()
        }
        timers: dict[str, dict[str, float]] = {}
        for (name, labels), values in _timers.items():
            count = values["count"]
            timers[_render_key(name, labels)] = {
                "count": int(count),
                "sum": values["sum"],
                "min": values["min"],
                "max": values["max"],
                "avg": values["sum"] / count if count else 0.0,
            }
    return {"counters": counters, "timers_ms": timers}


def reset() -> None:
    with _lock:
        _counters.clear()
        _timers.clear()
