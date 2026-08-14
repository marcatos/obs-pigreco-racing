"""Unit tests for flag director domain (no OBS)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "obs_flag_director"))

from domain_flag_director import FlagDirector, FlagDirectorConfig  # noqa: E402


def _dir(**kw) -> FlagDirector:
    cfg = FlagDirectorConfig(
        scenes={
            "yellow": "Flag Yellow",
            "red": "Flag Red",
            "checkered": "Flag Checkered",
        },
        home_scene="Rec * Live",
        debounce_ms=1500,
    )
    return FlagDirector(cfg)


def test_yellow_then_green_returns_home():
    d = _dir()
    assert d.on_flag("yellow", now_ms=1000) == "Flag Yellow"
    assert d.on_flag("yellow", now_ms=1100) is None  # same flag
    assert d.on_flag("green", now_ms=1200) is None  # debounce
    assert d.on_flag("green", now_ms=3000) == "Rec * Live"


def test_red_and_checkered():
    d = _dir()
    assert d.on_flag("red", now_ms=1000) == "Flag Red"
    assert d.on_flag("checkered", now_ms=3000) == "Flag Checkered"


def test_blue_no_scene_change():
    d = _dir()
    assert d.on_flag("blue", now_ms=1000) is None


def test_stacked_home_from_note_obs_scene():
    d = _dir()
    d.note_obs_scene("Live Race")
    assert d.on_flag("yellow", now_ms=1000) == "Flag Yellow"
    assert d.on_flag("green", now_ms=3000) == "Live Race"


def test_missing_scene_mapping_noop():
    d = FlagDirector(
        FlagDirectorConfig(scenes={"yellow": "Flag Yellow"}, home_scene="Home", debounce_ms=0)
    )
    assert d.on_flag("red", now_ms=1) is None
