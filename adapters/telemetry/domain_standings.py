"""Pure helpers for telemetry.tick standings / relatives (no IO)."""

from __future__ import annotations

from typing import Any


def format_gap_ms(gap_ms: float | None) -> float | None:
    if gap_ms is None:
        return None
    return int(round(gap_ms))


def build_relatives(
    standings: list[dict[str, Any]],
    *,
    focus_car_idx: int | None,
    window: int = 2,
) -> list[dict[str, Any]]:
    """Short list around focus: ahead (-n..-1), focus (0), behind (1..n)."""
    if not standings:
        return []
    focus_i = None
    for i, row in enumerate(standings):
        if focus_car_idx is not None and row.get("carIdx") == focus_car_idx:
            focus_i = i
            break
        if row.get("isFocus"):
            focus_i = i
            break
    if focus_i is None:
        focus_i = 0

    out: list[dict[str, Any]] = []
    for i in range(max(0, focus_i - window), min(len(standings), focus_i + window + 1)):
        row = standings[i]
        rel = i - focus_i
        gap = row.get("intervalMs")
        if rel == 0:
            gap_ms = 0
        elif rel < 0:
            # ahead of focus: sum intervals from i+1..focus
            gap_ms = 0
            for j in range(i + 1, focus_i + 1):
                gap_ms += int(standings[j].get("intervalMs") or 0)
            gap_ms = -gap_ms
        else:
            gap_ms = 0
            for j in range(focus_i + 1, i + 1):
                gap_ms += int(standings[j].get("intervalMs") or 0)
        out.append(
            {
                "rel": rel,
                "carNumber": row.get("carNumber") or "",
                "name": row.get("name") or "",
                "gapMs": gap_ms,
                "carIdx": row.get("carIdx"),
            }
        )
    return out


def mock_standings(elapsed_s: float, *, focus_pos: int, field: int = 12) -> list[dict[str, Any]]:
    """Deterministic fake leaderboard for overlay smoke tests."""
    import math

    wave = math.sin(elapsed_s * 0.35)
    others = [
        ("7", "Rossi"),
        ("23", "Bianchi"),
        ("11", "Verdi"),
        ("88", "Neri"),
        ("5", "Gialli"),
        ("16", "Blu"),
        ("99", "Grigi"),
        ("3", "Viola"),
        ("21", "Arancio"),
        ("44", "Celesti"),
        ("55", "Marroni"),
    ]
    focus_pos = max(1, min(int(focus_pos), field))
    field = max(2, min(field, 1 + len(others)))
    leader_best = 90801
    rows: list[dict[str, Any]] = []
    other_i = 0
    for pos in range(1, field + 1):
        if pos == focus_pos:
            num, name, car_idx, is_focus = "42", "S.Marcato", 1, True
        else:
            num, name = others[other_i % len(others)]
            other_i += 1
            car_idx, is_focus = pos + 10, False
        gap_to_leader = 0 if pos == 1 else int(1200 + (pos - 1) * (850 + wave * 40))
        interval = 0 if pos == 1 else int(800 + wave * 50 + (pos % 3) * 30)
        rows.append(
            {
                "pos": pos,
                "carNumber": num,
                "name": name,
                "gapMs": gap_to_leader,
                "intervalMs": interval,
                "lastLapMs": leader_best + int(pos * 120 + wave * 30),
                "bestLapMs": leader_best + int((pos - 1) * 90),
                "class": "GT3",
                "carIdx": car_idx,
                "isFocus": is_focus,
            }
        )
    return rows


def standings_from_cars(
    cars: list[dict[str, Any]],
    *,
    focus_car_idx: int | None,
    use_official_pos: bool,
    est_lap_ms: float = 90000.0,
) -> list[dict[str, Any]]:
    """Build standings from per-car snapshots.

    Each car dict: carIdx, name, carNumber, class, lap, distPct, surface,
    officialPos (optional), lastLapMs, bestLapMs.
    Sort: official positions if use_official_pos and all valid (>0),
    else by (lap + distPct) descending (replay-safe).
    Gaps estimated from distance delta * est_lap_ms.
    """
    active = [
        c
        for c in cars
        if c.get("carIdx") is not None
        and int(c.get("lap") or -1) >= 0
        and float(c.get("distPct") or -1) >= 0
    ]
    if not active:
        return []

    official_ok = use_official_pos and all(
        isinstance(c.get("officialPos"), (int, float)) and int(c["officialPos"]) > 0
        for c in active
    )
    if official_ok:
        ordered = sorted(active, key=lambda c: int(c["officialPos"]))
    else:
        ordered = sorted(
            active,
            key=lambda c: (int(c.get("lap") or 0) + float(c.get("distPct") or 0.0)),
            reverse=True,
        )

    rows: list[dict[str, Any]] = []
    leader_progress = int(ordered[0].get("lap") or 0) + float(ordered[0].get("distPct") or 0.0)
    prev_progress = leader_progress
    for i, c in enumerate(ordered):
        progress = int(c.get("lap") or 0) + float(c.get("distPct") or 0.0)
        gap_laps = leader_progress - progress
        interval_laps = prev_progress - progress if i > 0 else 0.0
        gap_ms = 0 if i == 0 else int(gap_laps * est_lap_ms)
        interval_ms = 0 if i == 0 else int(interval_laps * est_lap_ms)
        rows.append(
            {
                "pos": i + 1,
                "carNumber": str(c.get("carNumber") or ""),
                "name": str(c.get("name") or ""),
                "gapMs": gap_ms,
                "intervalMs": max(0, interval_ms),
                "lastLapMs": c.get("lastLapMs"),
                "bestLapMs": c.get("bestLapMs"),
                "class": c.get("class"),
                "carIdx": c.get("carIdx"),
                "isFocus": focus_car_idx is not None and c.get("carIdx") == focus_car_idx,
            }
        )
        prev_progress = progress
    return rows
