"""Cost and resource evidence for RSI rounds.

Provider-specific token and tool telemetry is optional.  Missing telemetry is
represented explicitly as ``unavailable`` instead of being turned into zero.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def _directory_size(root: Path) -> int:
    total = 0
    if not root.exists():
        return total
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total


def _unavailable() -> dict[str, Any]:
    return {"value": None, "status": "unavailable"}


def measure_round_cost(root: str | Path, started_at: float, *, render_status: str = "unavailable") -> dict[str, Any]:
    """Return a stable, JSON-friendly resource record for one round."""

    round_root = Path(root)
    return {
        "token_count": _unavailable(),
        "tool_calls": _unavailable(),
        "steps": _unavailable(),
        "wall_time_seconds": {
            "value": round(time.perf_counter() - started_at, 6),
            "status": "available",
        },
        "disk_bytes": {"value": _directory_size(round_root), "status": "available"},
        "render_cost": {
            "value": None,
            "status": render_status if render_status in {"available", "unavailable"} else "unavailable",
        },
    }


__all__ = ["measure_round_cost"]
