"""Battle panel session eligibility."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

from domain_battle import battle_panel_eligible  # noqa: E402


def test_quali_always_off():
    assert battle_panel_eligible("quali", live_order_ready=True, other_cars=10) is False


def test_cooldown_unknown_off():
    assert battle_panel_eligible("cooldown", live_order_ready=True, other_cars=5) is False
    assert battle_panel_eligible("unknown", live_order_ready=True, other_cars=5) is False


def test_practice_requires_others():
    assert battle_panel_eligible("practice", live_order_ready=True, other_cars=0) is False
    assert battle_panel_eligible("practice", live_order_ready=True, other_cars=1) is True


def test_race_requires_live_order():
    assert battle_panel_eligible("race", live_order_ready=False, other_cars=20) is False
    assert battle_panel_eligible("race", live_order_ready=True, other_cars=20) is True
