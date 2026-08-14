"""Unit tests for grid / rolling-start helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEL = ROOT / "adapters" / "telemetry"
sys.path.insert(0, str(TEL))

from domain_grid import (  # noqa: E402
    apply_start_positions,
    parse_qualify_grid,
    race_live_order_ready,
    standings_from_grid_order,
)


def test_parse_qualify_grid_zero_based():
    raw = {
        "Results": [
            {"CarIdx": 5, "Position": 0},
            {"CarIdx": 2, "Position": 1},
            {"CarIdx": 9, "Position": 2},
        ]
    }
    g = parse_qualify_grid(raw)
    assert g[5] == 1
    assert g[2] == 2
    assert g[9] == 3


def test_pos_change_vs_start():
    rows = apply_start_positions(
        [
            {"carIdx": 5, "pos": 3, "name": "A"},
            {"carIdx": 2, "pos": 1, "name": "B"},
        ],
        {5: 1, 2: 2},
    )
    assert rows[0]["startPos"] == 1
    assert rows[0]["posChange"] == -2  # started 1, now 3
    assert rows[1]["posChange"] == 1  # started 2, now 1


def test_live_order_gated_until_lap1():
    cars = [
        {"carIdx": 1, "lap": 0, "distPct": 0.1},
        {"carIdx": 2, "lap": 0, "distPct": 0.2},
        {"carIdx": 3, "lap": 0, "distPct": 0.3},
    ]
    assert (
        race_live_order_ready(
            session_kind="race",
            session_state=4,
            pace_mode=4,
            cars=cars,
        )
        is False
    )
    cars[0]["lap"] = 1
    cars[1]["lap"] = 1
    assert (
        race_live_order_ready(
            session_kind="race",
            session_state=4,
            pace_mode=4,
            cars=cars,
        )
        is True
    )


def test_parade_not_live():
    cars = [{"carIdx": 1, "lap": 1, "distPct": 0.5}]
    assert (
        race_live_order_ready(
            session_kind="race",
            session_state=3,  # parade
            pace_mode=0,
            cars=cars,
        )
        is False
    )


def test_grid_standings_hold():
    cars = [
        {"carIdx": 9, "lap": 0, "distPct": 0.9, "carNumber": "9", "name": "Z"},
        {"carIdx": 1, "lap": 0, "distPct": 0.1, "carNumber": "1", "name": "A"},
    ]
    rows = standings_from_grid_order(cars, focus_car_idx=1, start_by_car={1: 1, 9: 2})
    assert [r["carIdx"] for r in rows] == [1, 9]
    assert rows[0]["posChange"] == 0
    assert rows[0]["gapMs"] == 0
