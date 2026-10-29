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


def usage_from_legacy_costs(costs: dict):
    """Adapt old cost channels without converting absent observations into zero."""
    from .run_contracts import RunUsage

    mapping = {"token_count": "tokens", "tool_calls": "tool_calls", "steps": "steps",
               "wall_time_seconds": "wall_seconds", "cost_usd": "cost_usd"}
    values, statuses = {}, {}
    for old, new in mapping.items():
        channel = costs.get(old) or {}
        observed = channel.get("status") == "available" and channel.get("value") is not None
        values[new] = channel["value"] if observed else None
        statuses[new] = "available" if observed else "unavailable"
    return RunUsage(**values, statuses=statuses)


__all__ = ["measure_round_cost", "usage_from_legacy_costs"]
