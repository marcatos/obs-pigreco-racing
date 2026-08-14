# tests/test_telemetry_events.py
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

from domain_events import EventDetector, PRIORITIES


def _tick(**kw):
    base = {
        "type": "telemetry.tick",
        "schemaVersion": 1,
        "ts": 1_000_000,
        "flag": "green",
        "position": 4,
        "gapAheadMs": 2500,
        "gapBehindMs": 2500,
        "lastLapMs": 91000,
        "bestLapMs": 90000,
        "inPit": False,
        "focusCarNumber": "42",
    }
    base.update(kw)
    return base


def test_flag_change_emits_once():
    d = EventDetector(sensitivity="normal")
    assert d.feed(_tick(flag="green", ts=1)) == []
    ev = d.feed(_tick(flag="yellow", ts=2))
    assert len(ev) == 1
    assert ev[0]["kind"] == "flag_change"
    assert ev[0]["priority"] == PRIORITIES["flag_change"]
    assert ev[0]["payload"]["flag"] == "yellow"
    assert ev[0]["payload"]["prev"] == "green"
    assert d.feed(_tick(flag="yellow", ts=3)) == []


def test_battle_requires_streak():
    d = EventDetector(sensitivity="hype")  # battle_ticks=3
    assert d.feed(_tick(gapAheadMs=500, ts=10)) == []
    assert d.feed(_tick(gapAheadMs=500, ts=11)) == []
    ev = d.feed(_tick(gapAheadMs=500, ts=12))
    assert any(e["kind"] == "battle" for e in ev)


def test_overtake_on_position_improve():
    d = EventDetector()
    d.feed(_tick(position=5, ts=20))
    ev = d.feed(_tick(position=4, ts=21))
    assert any(e["kind"] == "overtake" and e["payload"]["fromPos"] == 5 for e in ev)


def test_fast_lap_when_last_le_best():
    d = EventDetector()
    d.feed(_tick(lastLapMs=91000, bestLapMs=90000, ts=30))
    ev = d.feed(_tick(lastLapMs=89900, bestLapMs=89900, ts=31))
    assert any(e["kind"] == "fast_lap" for e in ev)


def test_debounce_suppresses_repeat_battle():
    d = EventDetector(sensitivity="hype")
    for t in range(3):
        d.feed(_tick(gapAheadMs=400, ts=100 + t))
    # first battle likely at ts=102; immediate re-feed should debounce
    more = []
    for t in range(3, 6):
        more.extend(d.feed(_tick(gapAheadMs=400, ts=100 + t)))
    assert not any(e["kind"] == "battle" for e in more)


def test_mock_tick_sequence_can_yield_flag_event():
    from domain_events import EventDetector
    from mock_server import build_tick
    d = EventDetector(sensitivity="normal")
    # find yellow window: int(elapsed) % 47 in (12,13,14)
    d.feed(build_tick(11.0))
    ev = d.feed(build_tick(12.0))
    assert any(e["kind"] == "flag_change" for e in ev)


def test_pit_enter_exit():
    d = EventDetector()
    d.feed(_tick(inPit=False, ts=50))
    ev = d.feed(_tick(inPit=True, ts=51))
    assert any(e["kind"] == "pit" and e["payload"]["state"] == "enter" for e in ev)
    ev2 = d.feed(_tick(inPit=False, ts=52))
    assert any(e["kind"] == "pit" and e["payload"]["state"] == "exit" for e in ev2)


def test_mock_pit_window_emits_enter_and_exit():
    from mock_server import build_tick

    assert build_tick(39.0)["inPit"] is False
    assert build_tick(40.0)["inPit"] is True
    assert build_tick(44.0)["inPit"] is True
    assert build_tick(45.0)["inPit"] is False
    d = EventDetector()
    d.feed(build_tick(39.0))
    ev = d.feed(build_tick(40.0))
    assert any(e["kind"] == "pit" and e["payload"]["state"] == "enter" for e in ev)
    d.feed(build_tick(44.0))
    ev2 = d.feed(build_tick(45.0))
    assert any(e["kind"] == "pit" and e["payload"]["state"] == "exit" for e in ev2)


def test_mock_and_bridge_accept_sensitivity_flag():
    from mock_server import parse_args as mock_parse
    from iracing_bridge import parse_args as bridge_parse

    mock_default = mock_parse([])
    assert mock_default.sensitivity == "normal"
    mock_hype = mock_parse(["--sensitivity", "hype"])
    assert mock_hype.sensitivity == "hype"

    bridge_default = bridge_parse([])
    assert bridge_default.sensitivity == "normal"
    bridge_calm = bridge_parse(["--sensitivity", "calm"])
    assert bridge_calm.sensitivity == "calm"
