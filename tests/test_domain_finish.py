"""Finish-order latch under checkered — unit tests (no SDK)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

from domain_finish import (  # noqa: E402
    finish_phase_active,
    standings_from_finish_latch,
    update_finish_latch,
)


def test_finish_phase_active_on_checkered_flag():
    assert finish_phase_active(
        session_kind="race", flag="checkered", session_state=4
    )
    assert not finish_phase_active(
        session_kind="race", flag="green", session_state=4
    )
    assert finish_phase_active(
        session_kind="race", flag="green", session_state=5
    )
    assert finish_phase_active(
        session_kind="race", flag="green", session_state=6
    )
    assert not finish_phase_active(
        session_kind="practice", flag="checkered", session_state=5
    )


def test_last_car_alone_keeps_latched_finish_pos():
    """After field leaves, remaining last-place car must not become P1."""
    latch: dict = {}
    high = 0
    full_field = [
        {
            "carIdx": 1,
            "pos": 1,
            "officialPos": 1,
            "name": "Leader",
            "carNumber": "1",
        },
        {
            "carIdx": 2,
            "pos": 2,
            "officialPos": 2,
            "name": "Mid",
            "carNumber": "7",
        },
        {
            "carIdx": 9,
            "pos": 20,
            "officialPos": 20,
            "name": "Last",
            "carNumber": "42",
        },
    ]
    latch, high = update_finish_latch(latch, live_rows=full_field, field_high_water=high)
    assert high == 3
    assert latch[9]["pos"] == 20

    # Others left; SDK would re-rank the survivor as P1.
    alone = [
        {
            "carIdx": 9,
            "pos": 1,
            "officialPos": 1,
            "name": "Last",
            "carNumber": "42",
        }
    ]
    latch, high = update_finish_latch(latch, live_rows=alone, field_high_water=high)
    assert high == 3
    assert latch[9]["pos"] == 20
    assert latch[1]["pos"] == 1
    assert latch[2]["pos"] == 2

    board = standings_from_finish_latch(
        latch, focus_car_idx=9, present_idxs={9}
    )
    focus = next(r for r in board if r["isFocus"])
    assert focus["pos"] == 20
    assert focus["carNumber"] == "42"
    assert len(board) == 3


def test_under_checkered_can_still_worsen_while_field_full():
    latch: dict = {}
    high = 0
    rows = [
        {"carIdx": 9, "pos": 5, "officialPos": 5, "name": "A", "carNumber": "42"},
        {"carIdx": 1, "pos": 4, "officialPos": 4, "name": "B", "carNumber": "1"},
    ]
    latch, high = update_finish_latch(latch, live_rows=rows, field_high_water=high)
    rows[0]["officialPos"] = 6
    rows[0]["pos"] = 6
    latch, high = update_finish_latch(latch, live_rows=rows, field_high_water=high)
    assert latch[9]["pos"] == 6


def test_late_checkered_keeps_prior_latched_pos_when_field_thins():
    latch = {9: {"pos": 20, "carIdx": 9, "name": "Last", "carNumber": "42"}}
    alone = [
        {
            "carIdx": 9,
            "pos": 1,
            "officialPos": 1,
            "name": "Last",
            "carNumber": "42",
        }
    ]
    latch, high = update_finish_latch(latch, live_rows=alone, field_high_water=20)
    assert latch[9]["pos"] == 20
    assert high == 20


def test_bridge_wires_finish_latch():
    src = (
        Path(__file__).resolve().parents[1]
        / "adapters"
        / "telemetry"
        / "iracing_bridge.py"
    ).read_text(encoding="utf-8")
    assert "domain_finish" in src
    assert "update_finish_latch" in src
    assert "standings_from_finish_latch" in src
    assert "_finish_latch" in src
