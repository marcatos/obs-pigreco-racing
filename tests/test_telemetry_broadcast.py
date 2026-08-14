"""Unit tests for telemetry standings helpers (no iRacing SDK)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEL = ROOT / "adapters" / "telemetry"
sys.path.insert(0, str(TEL))

from domain_standings import (  # noqa: E402
    build_relatives,
    mock_standings,
    standings_from_cars,
)
from mock_server import build_tick  # noqa: E402


def test_mock_standings_focus_position():
    rows = mock_standings(10.0, focus_pos=3, field=8)
    assert len(rows) == 8
    focus = [r for r in rows if r["isFocus"]]
    assert len(focus) == 1
    assert focus[0]["pos"] == 3
    assert focus[0]["carNumber"] == "42"


def test_build_tick_has_broadcast_fields():
    tick = build_tick(5.0)
    assert tick["type"] == "telemetry.tick"
    assert tick["schemaVersion"] == 1
    assert tick["isReplay"] is True
    assert isinstance(tick["standings"], list)
    assert len(tick["standings"]) >= 5
    assert isinstance(tick["relatives"], list)
    assert tick["focusDriverName"]
    assert tick.get("trackId") == "900001"
    assert isinstance(tick.get("mapCars"), list)
    assert len(tick["mapCars"]) >= 5


def test_standings_from_distance_replay_order():
    cars = [
        {
            "carIdx": 2,
            "name": "A",
            "carNumber": "1",
            "lap": 10,
            "distPct": 0.2,
            "officialPos": -1,
            "lastLapMs": 90000,
            "bestLapMs": 89000,
            "class": "GT3",
        },
        {
            "carIdx": 5,
            "name": "B",
            "carNumber": "42",
            "lap": 10,
            "distPct": 0.9,
            "officialPos": -1,
            "lastLapMs": 91000,
            "bestLapMs": 90000,
            "class": "GT3",
        },
        {
            "carIdx": 7,
            "name": "C",
            "carNumber": "7",
            "lap": 9,
            "distPct": 0.99,
            "officialPos": -1,
            "lastLapMs": 92000,
            "bestLapMs": 91000,
            "class": "GT3",
        },
    ]
    rows = standings_from_cars(cars, focus_car_idx=5, use_official_pos=False)
    assert [r["carIdx"] for r in rows] == [5, 2, 7]
    assert rows[0]["isFocus"] is True
    assert rows[0]["pos"] == 1
    rel = build_relatives(rows, focus_car_idx=5, window=1)
    assert any(r["rel"] == 0 for r in rel)


def test_sanitize_laps_remain_sentinel():
    from iracing_bridge import _sanitize_laps_remain

    assert _sanitize_laps_remain(32767) is None
    assert _sanitize_laps_remain(32000) is None
    assert _sanitize_laps_remain(12) == 12
    assert _sanitize_laps_remain(-1) is None
    assert _sanitize_laps_remain(None) is None


def test_build_tick_enrichment_fields():
    tick = build_tick(5.0)
    assert "deltaBestMs" in tick
    assert tick["deltaBestMs"] == tick["lastLapMs"] - tick["bestLapMs"]
    assert isinstance(tick.get("inPit"), bool)
    assert tick["standings"][0].get("posChange") in (-1, 0, 1, None)
    # second call should populate posChange from prev
    tick2 = build_tick(6.0)
    assert any(r.get("posChange") is not None for r in tick2["standings"])
