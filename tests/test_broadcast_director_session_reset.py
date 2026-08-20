"""Overlay clear on telemetry.session_reset (Task 4)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_clear_director_state_in_js():
    src = (ROOT / "overlays" / "broadcast-director.js").read_text(encoding="utf-8")
    assert "clearDirectorState" in src
    br = (ROOT / "overlays" / "broadcast.js").read_text(encoding="utf-8")
    assert "telemetry.session_reset" in br
    assert "clearLeaderboardDom" in br
    assert 'clearSessionOverlayState("ws_open")' in br
    assert "elLb.innerHTML" in br
