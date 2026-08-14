"""Pure telemetry.event detection from consecutive ticks (no IO)."""
from __future__ import annotations

from typing import Any

from domain_enrich import SENSITIVITY

PRIORITIES = {
    "flag_change": 100,
    "session_end": 90,
    "overtake": 80,
    "battle": 60,
    "fast_lap": 50,
    "pit": 40,
}
DEFAULT_TTL_MS = 4000


class EventDetector:
    def __init__(self, *, sensitivity: str = "normal") -> None:
        self.set_sensitivity(sensitivity)
        self._prev: dict[str, Any] | None = None
        self._battle_streak = 0
        self._last_emit_ms: dict[str, int] = {}
        self._seq = 0

    def set_sensitivity(self, name: str) -> None:
        key = name if name in SENSITIVITY else "normal"
        self._sens_name = key
        self._cfg = SENSITIVITY[key]

    def reset(self) -> None:
        """Drop consecutive-tick state. Keep sensitivity / config."""
        self._prev = None
        self._battle_streak = 0
        self._last_emit_ms = {}

    def feed(self, tick: dict[str, Any], *, now_ms: int | None = None) -> list[dict[str, Any]]:
        ts = int(now_ms if now_ms is not None else tick.get("ts") or 0)
        out: list[dict[str, Any]] = []
        prev = self._prev

        if prev is not None:
            out.extend(self._detect(prev, tick, ts))
        else:
            # First sample still counts toward battle_ticks (N close feeds → emit).
            self._update_battle_streak(tick)

        self._prev = dict(tick)
        return out

    def _debounced(self, kind: str, ts: int) -> bool:
        last = self._last_emit_ms.get(kind)
        if last is not None and (ts - last) < self._cfg["debounce_ms"]:
            return True
        return False

    def _emit(
        self,
        kind: str,
        ts: int,
        payload: dict[str, Any],
        *,
        debounce_key: str | None = None,
    ) -> dict[str, Any] | None:
        key = debounce_key or kind
        if self._debounced(key, ts):
            return None
        self._last_emit_ms[key] = ts
        self._seq += 1
        return {
            "type": "telemetry.event",
            "schemaVersion": 1,
            "ts": ts,
            "eventId": f"evt-{self._seq}",
            "kind": kind,
            "priority": PRIORITIES[kind],
            "ttlMs": DEFAULT_TTL_MS,
            "payload": payload,
        }

    def _gap_close(self, tick: dict[str, Any]) -> tuple[bool, int | None]:
        thr = self._cfg["battle_ms"]
        ga = tick.get("gapAheadMs")
        gb = tick.get("gapBehindMs")
        close = False
        gap_val: int | None = None
        if isinstance(ga, (int, float)) and 0 < ga <= thr:
            close, gap_val = True, int(ga)
        if isinstance(gb, (int, float)) and 0 < gb <= thr:
            if gap_val is None or gb < gap_val:
                close, gap_val = True, int(gb)
        return close, gap_val

    def _update_battle_streak(self, tick: dict[str, Any]) -> int | None:
        close, gap_val = self._gap_close(tick)
        if close:
            self._battle_streak += 1
        else:
            self._battle_streak = 0
        return gap_val if close else None

    def _detect(self, prev: dict[str, Any], tick: dict[str, Any], ts: int) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        pf = (prev.get("flag") or "none").lower()
        cf = (tick.get("flag") or "none").lower()
        if cf != pf:
            e = self._emit("flag_change", ts, {"flag": cf, "prev": pf})
            if e:
                found.append(e)
            if cf in ("checkered", "white"):
                e2 = self._emit("session_end", ts, {"flag": cf})
                if e2:
                    found.append(e2)

        gap_val = self._update_battle_streak(tick)
        if self._battle_streak >= self._cfg["battle_ticks"]:
            e = self._emit(
                "battle",
                ts,
                {"gapMs": gap_val, "withCarNumber": None},
            )
            if e:
                found.append(e)
                self._battle_streak = 0

        pp, cp = prev.get("position"), tick.get("position")
        if isinstance(pp, (int, float)) and isinstance(cp, (int, float)) and int(cp) < int(pp):
            e = self._emit(
                "overtake",
                ts,
                {"fromPos": int(pp), "toPos": int(cp)},
            )
            if e:
                found.append(e)

        pl, pb = prev.get("lastLapMs"), prev.get("bestLapMs")
        cl, cb = tick.get("lastLapMs"), tick.get("bestLapMs")
        if (
            isinstance(cl, (int, float))
            and isinstance(cb, (int, float))
            and cl <= cb
            and (pl != cl or pb != cb)
        ):
            e = self._emit("fast_lap", ts, {"lapMs": int(cl)})
            if e:
                found.append(e)

        ppit = prev.get("inPit")
        cpit = tick.get("inPit")
        if ppit is not None and cpit is not None:
            was_pit = bool(ppit)
            now_pit = bool(cpit)
            if now_pit and not was_pit:
                e = self._emit("pit", ts, {"state": "enter"}, debounce_key="pit:enter")
                if e:
                    found.append(e)
            elif was_pit and not now_pit:
                e = self._emit("pit", ts, {"state": "exit"}, debounce_key="pit:exit")
                if e:
                    found.append(e)

        return found
