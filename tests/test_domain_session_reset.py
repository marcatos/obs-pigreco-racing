from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

from domain_session_reset import (  # noqa: E402
    SessionResetTracker,
    build_session_key,
    session_reset_envelope,
)


def test_build_session_key_prefers_unique_id():
    assert (
        build_session_key(
            unique_id="UID-9",
            track_id=123,
            session_num=2,
            session_kind="race",
        )
        == "UID-9"
    )


def test_build_session_key_fallback_tuple():
    k = build_session_key(
        unique_id=None,
        track_id=42,
        session_num=1,
        session_kind="race",
    )
    assert k == "42:1:race"


def test_build_session_key_none_when_unstable():
    assert (
        build_session_key(
            unique_id=None,
            track_id=None,
            session_num=None,
            session_kind=None,
        )
        is None
    )


def test_tracker_first_latch_no_emit():
    t = SessionResetTracker(debounce_ms=1500)
    assert t.note("A", now_ms=1000) is None
    assert t.current_key == "A"


def test_tracker_key_change_emits_once():
    t = SessionResetTracker(debounce_ms=1500)
    t.note("A", now_ms=1000)
    ev = t.note("B", now_ms=3000)
    assert ev is not None
    assert ev["reason"] == "session_changed"
    assert ev["sessionKey"] == "B"
    assert ev["previousKey"] == "A"
    assert t.note("B", now_ms=3500) is None


def test_tracker_debounce_collapses_rapid_changes():
    t = SessionResetTracker(debounce_ms=1500)
    t.note("A", now_ms=1000)
    assert t.note("B", now_ms=1100) is not None
    assert t.note("C", now_ms=1200) is None  # within debounce
    assert t.current_key == "B"  # ignored flicker keeps last emitted key
    # After debounce, C can emit
    ev = t.note("C", now_ms=3000)
    assert ev is not None
    assert ev["sessionKey"] == "C"


def test_tracker_force_manual():
    t = SessionResetTracker(debounce_ms=1500)
    t.note("A", now_ms=1000)
    ev = t.force(reason="manual", now_ms=1500)
    assert ev["reason"] == "manual"
    assert ev["sessionKey"] == "A"


def test_session_reset_envelope_shape():
    msg = session_reset_envelope(
        reason="session_changed",
        session_key="B",
        previous_key="A",
        ts=99,
    )
    assert msg["type"] == "telemetry.session_reset"
    assert msg["schemaVersion"] == 1
    assert msg["ts"] == 99
    assert msg["reason"] == "session_changed"
    assert msg["sessionKey"] == "B"
    assert msg["previousKey"] == "A"
