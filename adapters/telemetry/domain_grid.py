"""Grid / rolling-start helpers (pure, no IO)."""

from __future__ import annotations

from typing import Any

# irsdk.SessionState.racing
_STATE_RACING = 4
# irsdk.PaceMode.not_pacing
_PACE_NOT_PACING = 4


def _lap_int(car: dict[str, Any]) -> int:
    """Lap 0 is valid (formation); do not treat falsy 0 as missing."""
    lap = car.get("lap")
    if lap is None:
        return -1
    try:
        return int(lap)
    except (TypeError, ValueError):
        return -1


def parse_qualify_grid(raw: Any) -> dict[int, int]:
    """Map CarIdx → 1-based overall start position from QualifyResultsInfo."""
    out: dict[int, int] = {}
    if not raw:
        return out
    results = raw
    if isinstance(raw, dict):
        results = raw.get("Results") or raw.get("results") or []
    if not isinstance(results, (list, tuple)):
        return out
    parsed: list[tuple[int, int]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        try:
            car_idx = int(item.get("CarIdx"))
            pos = int(item.get("Position", item.get("position")))
        except (TypeError, ValueError):
            continue
        if car_idx < 0 or pos < 0:
            continue
        parsed.append((car_idx, pos))
    if not parsed:
        return out
    zero_based = min(p for _, p in parsed) == 0
    for car_idx, pos in parsed:
        out[car_idx] = pos + 1 if zero_based else pos
    return out


def race_live_order_ready(
    *,
    session_kind: str,
    session_state: int | None,
    pace_mode: int | None,
    cars: list[dict[str, Any]],
    min_frac_lap1: float = 0.4,
) -> bool:
    """False during formation / pace / until enough cars crossed S/F (lap >= 1)."""
    if session_kind != "race":
        return True
    try:
        state = int(session_state) if session_state is not None else None
    except (TypeError, ValueError):
        state = None
    if state is not None and state < _STATE_RACING:
        return False
    try:
        pace = int(pace_mode) if pace_mode is not None else None
    except (TypeError, ValueError):
        pace = None
    if pace is not None and pace != _PACE_NOT_PACING:
        return False

    active = [c for c in cars if c.get("carIdx") is not None and _lap_int(c) >= 0]
    if not active:
        return False
    on_race_lap = sum(1 for c in active if _lap_int(c) >= 1)
    need = max(1, int(round(len(active) * min_frac_lap1)))
    return on_race_lap >= need


def apply_start_positions(
    standings: list[dict[str, Any]],
    start_by_car: dict[Any, int] | None,
    *,
    show_delta: bool = True,
) -> list[dict[str, Any]]:
    """Attach startPos and posChange (places gained vs grid start).

    ``start_by_car`` keys may be ``carIdx`` (int) and/or ``carNumber`` (str).
    """
    starts = start_by_car or {}
    out: list[dict[str, Any]] = []
    for row in standings:
        r = dict(row)
        start = None
        key = r.get("carIdx")
        if key is not None:
            try:
                start = starts.get(int(key))
            except (TypeError, ValueError):
                start = starts.get(key)
        if start is None and r.get("carNumber") is not None:
            start = starts.get(str(r.get("carNumber")))
        r["startPos"] = int(start) if start is not None else None
        change = None
        pos = r.get("pos")
        if (
            show_delta
            and start is not None
            and isinstance(pos, (int, float))
            and int(pos) > 0
        ):
            change = int(start) - int(pos)
        r["posChange"] = change
        out.append(r)
    return out


def order_cars_by_start(
    cars: list[dict[str, Any]],
    start_by_car: dict[int, int],
) -> list[dict[str, Any]]:
    """Stable grid order for pre-green / rolling-start hold."""

    def sort_key(c: dict[str, Any]) -> tuple[int, int]:
        try:
            i = int(c.get("carIdx"))
        except (TypeError, ValueError):
            return (10_000, 0)
        sp = start_by_car.get(i)
        if sp is None:
            return (9_000 + i, i)
        return (int(sp), i)

    return sorted(cars, key=sort_key)


def standings_from_grid_order(
    cars: list[dict[str, Any]],
    *,
    focus_car_idx: int | None,
    start_by_car: dict[int, int],
) -> list[dict[str, Any]]:
    """Leaderboard frozen to starting grid (no live gaps)."""
    ordered = order_cars_by_start(
        [
            c
            for c in cars
            if c.get("carIdx") is not None
            and _lap_int(c) >= 0
            and float(c["distPct"] if c.get("distPct") is not None else -1) >= 0
        ],
        start_by_car,
    )
    rows: list[dict[str, Any]] = []
    for i, c in enumerate(ordered):
        try:
            idx = int(c["carIdx"])
        except (TypeError, ValueError):
            continue
        start = start_by_car.get(idx, i + 1)
        rows.append(
            {
                "pos": i + 1,
                "carNumber": str(c.get("carNumber") or ""),
                "name": str(c.get("name") or ""),
                "clubName": (str(c.get("clubName") or "").strip() or None),
                "userId": c.get("userId"),
                "countryCode": c.get("countryCode"),
                "country": c.get("country"),
                "gapMs": 0 if i == 0 else None,
                "intervalMs": None,
                "lastLapMs": c.get("lastLapMs"),
                "bestLapMs": c.get("bestLapMs"),
                "class": c.get("class"),
                "carIdx": idx,
                "isFocus": focus_car_idx is not None and idx == focus_car_idx,
                "distPct": float(c.get("distPct") or 0.0) % 1.0,
                "startPos": int(start),
                "posChange": 0,
            }
        )
    return rows
