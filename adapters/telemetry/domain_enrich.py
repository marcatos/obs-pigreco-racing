"""Pure tick enrichment helpers (no IO)."""
from __future__ import annotations
from typing import Any

SENSITIVITY: dict[str, dict[str, int]] = {
    "calm": {"battle_ms": 1800, "battle_ticks": 8, "debounce_ms": 4000},
    "normal": {"battle_ms": 1200, "battle_ticks": 5, "debounce_ms": 3000},
    "hype": {"battle_ms": 800, "battle_ticks": 3, "debounce_ms": 2000},
}


def delta_best_ms(last_lap_ms: float | None, best_lap_ms: float | None) -> int | None:
    if last_lap_ms is None or best_lap_ms is None:
        return None
    try:
        return int(round(float(last_lap_ms) - float(best_lap_ms)))
    except (TypeError, ValueError):
        return None


def apply_pos_change(
    standings: list[dict[str, Any]],
    prev_pos_by_car: dict[Any, int] | None,
) -> tuple[list[dict[str, Any]], dict[Any, int]]:
    prev = prev_pos_by_car or {}
    out: list[dict[str, Any]] = []
    new_map: dict[Any, int] = {}
    for row in standings:
        r = dict(row)
        key = r.get("carIdx")
        if key is None:
            key = r.get("carNumber")
        pos = r.get("pos")
        change = None
        if key is not None and isinstance(pos, (int, float)):
            pos_i = int(pos)
            new_map[key] = pos_i
            if key in prev:
                delta = prev[key] - pos_i  # positive = gained places
                if delta > 0:
                    change = 1
                elif delta < 0:
                    change = -1
                else:
                    change = 0
        r["posChange"] = change
        out.append(r)
    return out, new_map
