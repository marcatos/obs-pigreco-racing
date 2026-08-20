"""Pure session identity + reset gating (no IO)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RESET_DEBOUNCE_MS = 1500


def build_session_key(
    *,
    unique_id: Any,
    track_id: Any,
    session_num: Any,
    session_kind: str | None,
) -> str | None:
    if unique_id is not None and str(unique_id).strip():
        return str(unique_id).strip()
    try:
        sn = int(session_num) if session_num is not None else None
    except (TypeError, ValueError):
        sn = None
    tid = None
    if track_id is not None and str(track_id).strip():
        tid = str(track_id).strip()
    kind = (session_kind or "unknown").strip().lower() or "unknown"
    if tid is None or sn is None:
        return None
    return f"{tid}:{sn}:{kind}"


def session_reset_envelope(
    *,
    reason: str,
    session_key: str | None,
    previous_key: str | None,
    ts: int,
) -> dict[str, Any]:
    return {
        "type": "telemetry.session_reset",
        "schemaVersion": 1,
        "ts": int(ts),
        "reason": reason,
        "sessionKey": session_key,
        "previousKey": previous_key,
    }


@dataclass
class SessionResetTracker:
    debounce_ms: int = RESET_DEBOUNCE_MS
    current_key: str | None = None
    _last_emit_ms: int = field(default=-10**12, repr=False)
    _warned_missing: bool = field(default=False, repr=False)

    def note(self, key: str | None, *, now_ms: int) -> dict[str, Any] | None:
        if key is None:
            return None
        if self.current_key is None:
            self.current_key = key
            return None
        if key == self.current_key:
            return None
        if (now_ms - self._last_emit_ms) < self.debounce_ms:
            return None
        prev = self.current_key
        self.current_key = key
        self._last_emit_ms = now_ms
        return {
            "reason": "session_changed",
            "sessionKey": key,
            "previousKey": prev,
        }

    def force(self, *, reason: str, now_ms: int) -> dict[str, Any]:
        self._last_emit_ms = now_ms
        return {
            "reason": reason,
            "sessionKey": self.current_key,
            "previousKey": self.current_key,
        }

    def clear_key(self) -> None:
        """On sim disconnect — next connect re-latches without emit if same key."""
        self.current_key = None
