"""Pure sector / split helpers (no IO)."""

from __future__ import annotations

from typing import Any


def normalize_sector_starts(raw: Any) -> list[float]:
    """Return sorted unique sector start fractions in [0, 1)."""
    starts: list[float] = []
    if not raw:
        return starts
    items = raw
    if isinstance(raw, dict):
        items = raw.get("Sectors") or raw.get("sectors") or []
    if not isinstance(items, (list, tuple)):
        return starts
    for item in items:
        pct: Any = None
        if isinstance(item, dict):
            pct = item.get("SectorStartPct", item.get("startPct"))
        else:
            pct = item
        try:
            v = float(pct)
        except (TypeError, ValueError):
            continue
        if not (0.0 <= v < 1.0):
            continue
        starts.append(v)
    starts = sorted(set(round(s, 6) for s in starts))
    if starts and starts[0] > 0.001:
        starts.insert(0, 0.0)
    elif not starts:
        return []
    elif starts[0] != 0.0:
        starts[0] = 0.0
    return starts


def sectors_payload(starts: list[float]) -> list[dict[str, float | int]]:
    return [{"num": i + 1, "startPct": float(starts[i])} for i in range(len(starts))]


def current_sector(dist_pct: float | None, starts: list[float]) -> int | None:
    """1-based sector index for LapDistPct, or None if unknown."""
    if not starts or dist_pct is None:
        return None
    try:
        t = float(dist_pct) % 1.0
    except (TypeError, ValueError):
        return None
    if t < 0:
        t += 1.0
    idx = 0
    for i, s in enumerate(starts):
        if t >= s:
            idx = i
        else:
            break
    return idx + 1


def sector_deltas_ms(
    last_ms: list[int | None] | None,
    best_ms: list[int | None] | None,
) -> list[int | None] | None:
    if not last_ms or not best_ms:
        return None
    n = min(len(last_ms), len(best_ms))
    if n <= 0:
        return None
    out: list[int | None] = []
    for i in range(n):
        a, b = last_ms[i], best_ms[i]
        if a is None or b is None:
            out.append(None)
        else:
            try:
                out.append(int(round(float(a) - float(b))))
            except (TypeError, ValueError):
                out.append(None)
    return out


def delta_live_ms(delta_s: Any, ok: Any) -> int | None:
    """LapDeltaToBestLap (seconds) → ms when OK flag is true."""
    if ok is False or ok == 0 or ok == "0":
        return None
    if ok is None and delta_s is None:
        return None
    try:
        v = float(delta_s)
    except (TypeError, ValueError):
        return None
    if not (abs(v) < 600.0):  # sanity: < 10 min
        return None
    return int(round(v * 1000.0))


class SectorLapTracker:
    """Latch per-sector times for the player car using lap clock + dist."""

    def __init__(self) -> None:
        self.starts: list[float] = []
        self._lap: int | None = None
        self._prev_dist: float | None = None
        self._open: list[int] = []  # completed sector durations this lap
        self._last: list[int] | None = None
        self._best: list[int] | None = None
        self._last_clock_ms: int | None = None

    def reset(self) -> None:
        self._lap = None
        self._prev_dist = None
        self._open = []
        self._last_clock_ms = None
        # keep starts + best/last memory across soft resets; clear times on hard reset
        self._last = None
        self._best = None

    def set_starts(self, starts: list[float]) -> None:
        if list(starts) != self.starts:
            self.starts = list(starts)
            self._open = []
            self._prev_dist = None
            self._lap = None

    def _update_best(self, sectors: list[int]) -> None:
        if not sectors:
            return
        if self._best is None or len(self._best) != len(sectors):
            self._best = list(sectors)
            return
        for i, v in enumerate(sectors):
            if self._best[i] is None or v < self._best[i]:
                self._best[i] = v

    def _finalize_lap(self, last_lap_ms: int | None) -> None:
        n = len(self.starts)
        if n <= 0:
            self._open = []
            return
        if len(self._open) == n - 1 and last_lap_ms is not None:
            try:
                rem = int(round(float(last_lap_ms))) - sum(self._open)
            except (TypeError, ValueError):
                rem = 0
            if rem > 50:
                full = self._open + [rem]
                self._last = full
                self._update_best(full)
        elif len(self._open) == n:
            self._last = list(self._open)
            self._update_best(self._open)
        self._open = []

    def update(
        self,
        *,
        dist_pct: float | None,
        current_lap_ms: float | None,
        lap: int | None,
        last_lap_ms: float | None = None,
    ) -> dict[str, Any]:
        """Advance tracker; return snapshot fields for the tick."""
        starts = self.starts
        sector = current_sector(dist_pct, starts)
        if not starts or dist_pct is None:
            return {
                "sector": sector,
                "lastSectorsMs": self._last,
                "bestSectorsMs": self._best,
                "sectorDeltaMs": sector_deltas_ms(self._last, self._best),
            }

        try:
            dist = float(dist_pct) % 1.0
            if dist < 0:
                dist += 1.0
        except (TypeError, ValueError):
            return {
                "sector": sector,
                "lastSectorsMs": self._last,
                "bestSectorsMs": self._best,
                "sectorDeltaMs": sector_deltas_ms(self._last, self._best),
            }

        clock: int | None = None
        if current_lap_ms is not None:
            try:
                clock = int(round(float(current_lap_ms)))
                if clock < 0:
                    clock = None
            except (TypeError, ValueError):
                clock = None

        lap_i: int | None = None
        if lap is not None:
            try:
                lap_i = int(lap)
            except (TypeError, ValueError):
                lap_i = None

        wrapped = (
            self._prev_dist is not None
            and self._prev_dist > 0.85
            and dist < 0.15
        )
        new_lap = lap_i is not None and self._lap is not None and lap_i > self._lap
        if wrapped or new_lap:
            self._finalize_lap(
                int(round(float(last_lap_ms))) if last_lap_ms is not None else None
            )

        if lap_i is not None:
            self._lap = lap_i

        n = len(starts)
        if clock is not None and self._prev_dist is not None:
            for i in range(1, n):
                boundary = starts[i]
                crossed = self._prev_dist < boundary <= dist
                # wrap already handled via finalize; mid-lap only
                if crossed and len(self._open) == i - 1:
                    dur = clock - sum(self._open)
                    if dur > 50:
                        self._open.append(dur)

        if clock is not None:
            self._last_clock_ms = clock
        self._prev_dist = dist

        return {
            "sector": sector,
            "lastSectorsMs": list(self._last) if self._last else None,
            "bestSectorsMs": list(self._best) if self._best else None,
            "sectorDeltaMs": sector_deltas_ms(self._last, self._best),
        }
