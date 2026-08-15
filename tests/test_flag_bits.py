"""SessionFlags → flag name mapping."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

import iracing_bridge as br  # noqa: E402


def test_debris_is_0x40_not_blue():
    assert br._flag_name(0x00000040) == "debris"


def test_blue_is_0x20():
    assert br._flag_name(0x00000020) == "blue"


def test_black_and_meatball_bits():
    assert br._flag_name(0x00010000) == "black"
    assert br._flag_name(0x00100000) == "meatball"


def test_checkered_beats_debris():
    assert br._flag_name(0x00000001 | 0x00000040) == "checkered"


def test_white_flag():
    assert br._flag_name(0x00000002) == "white"
