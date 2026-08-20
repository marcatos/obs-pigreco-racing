"""Finish-order latch under checkered (pure, no IO).

iRacing drops NotInWorld cars from the live field after they leave; ranking the
remaining cars 1..N then promotes the last driver still connected to P1.
Latch absolute positions while the field is still full and never rewrite them
to a better place once the field has thinned.
"""

from __future__ import annotations

from typing import Any

# irsdk.SessionState
_STATE_CHECKERED = 5
_STATE_COOLDOWN = 6


def finish_phase_active(
    *,
    session_kind: str,
    flag: str | None,
    session_state: int | None,
) -> bool:
    """True once checkered is out or the session is in checkered/cool-down."""
    if (session_kind or "").lower() != "race":
        return False
    f = (flag or "").strip().lower()
    if f == "checkered":
        return True
    try:
        state = int(session_state) if session_state is not None else None
    except (TypeError, ValueError):
        state = None
    return state is not None and state >= _STATE_CHECKERED


def _car_idx(row: dict[str, Any]) -> int | None:
    raw = row.get("carIdx")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _abs_pos(row: dict[str, Any]) -> int | None:
    """Prefer SDK officialPos; fall back to board pos."""
    for key in ("officialPos", "pos"):
        raw = row.get(key)
        try:
            pos = int(raw)
        except (TypeError, ValueError):
            continue
        if pos > 0:
            return pos
    return None


def update_finish_latch(
    latch: dict[int, dict[str, Any]],
    *,
    live_rows: list[dict[str, Any]],
    field_high_water: int,
) -> tuple[dict[int, dict[str, Any]], int]:
    """Merge live board into latch; return (latch, updated_high_water).

    - First sighting of a car: store absolute position + identity.
    - Still present with a fuller field (present >= high_water): allow updates.
    - Still present after the field thins: only allow position to worsen
      (got passed under checkered); never promote (e.g. alone → P1).
    - Cars that left keep their last latched row forever (until session reset).
    """
    present = 0
    live_by_idx: dict[int, dict[str, Any]] = {}
    for row in live_rows:
        idx = _car_idx(row)
        if idx is None:
            continue
        present += 1
        live_by_idx[idx] = row

    high = max(int(field_high_water or 0), present)
    field_full = present > 0 and present >= high

    out = dict(latch)
    for idx, row in live_by_idx.items():
        pos = _abs_pos(row)
        if pos is None:
            continue
        prev = out.get(idx)
        if prev is None:
            out[idx] = _snap_row(row, pos=pos)
            continue
        prev_pos = int(prev.get("pos") or 0)
        if pos > prev_pos:
            # Worsened under checkered — still racing / got passed.
            out[idx] = _snap_row(row, pos=pos, prev=prev)
        elif field_full and pos != prev_pos:
            out[idx] = _snap_row(row, pos=pos, prev=prev)
        else:
            # Keep latched pos; refresh identity/telemetry cosmetics if useful.
            out[idx] = _snap_row(row, pos=prev_pos, prev=prev)
    return out, high


def _snap_row(
    row: dict[str, Any],
    *,
    pos: int,
    prev: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = dict(prev) if prev else {}
    base.update(
        {
            "pos": int(pos),
            "carIdx": _car_idx(row),
            "carNumber": str(row.get("carNumber") or base.get("carNumber") or ""),
            "name": str(row.get("name") or base.get("name") or ""),
            "clubName": row.get("clubName", base.get("clubName")),
            "userId": row.get("userId", base.get("userId")),
            "countryCode": row.get("countryCode", base.get("countryCode")),
            "country": row.get("country", base.get("country")),
            "class": row.get("class", base.get("class")),
            "lastLapMs": row.get("lastLapMs", base.get("lastLapMs")),
            "bestLapMs": row.get("bestLapMs", base.get("bestLapMs")),
            "gapMs": row.get("gapMs", base.get("gapMs")),
            "intervalMs": row.get("intervalMs", base.get("intervalMs")),
            "distPct": row.get("distPct", base.get("distPct")),
            "speedKph": row.get("speedKph", base.get("speedKph")),
            "trackSurface": row.get("trackSurface", base.get("trackSurface")),
            "startPos": row.get("startPos", base.get("startPos")),
            "posChange": row.get("posChange", base.get("posChange")),
            "inPit": row.get("inPit", base.get("inPit")),
            "iRating": row.get("iRating", base.get("iRating")),
        }
    )
    return base


def standings_from_finish_latch(
    latch: dict[int, dict[str, Any]],
    *,
    focus_car_idx: int | None,
    present_idxs: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Board ordered by latched absolute finish positions (not reindexed 1..N)."""
    present = present_idxs or set()
    rows = sorted(
        (dict(v) for v in latch.values() if isinstance(v.get("pos"), (int, float))),
        key=lambda r: (int(r["pos"]), int(r.get("carIdx") or 0)),
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        idx = _car_idx(r)
        row = dict(r)
        row["pos"] = int(r["pos"])
        row["isFocus"] = focus_car_idx is not None and idx == focus_car_idx
        row["connected"] = idx in present if idx is not None else False
        out.append(row)
    return out
