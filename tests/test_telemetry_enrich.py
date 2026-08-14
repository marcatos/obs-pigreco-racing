# tests/test_telemetry_enrich.py
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

from domain_enrich import SENSITIVITY, apply_pos_change, delta_best_ms


def test_delta_best_ms():
    assert delta_best_ms(90100, 90000) == 100
    assert delta_best_ms(89900, 90000) == -100
    assert delta_best_ms(None, 90000) is None
    assert delta_best_ms(90000, None) is None


def test_apply_pos_change_gain_and_loss():
    prev = {1: 3, 2: 1}
    rows = [
        {"carIdx": 1, "pos": 2},
        {"carIdx": 2, "pos": 1},
    ]
    out, new_map = apply_pos_change(rows, prev)
    assert out[0]["posChange"] == 1   # 3 → 2 improved
    assert out[1]["posChange"] == 0   # still P1
    assert new_map[1] == 2


def test_sensitivity_keys():
    assert set(SENSITIVITY) == {"calm", "normal", "hype"}
    assert SENSITIVITY["normal"]["battle_ms"] == 1200
    assert SENSITIVITY["calm"]["battle_ms"] > SENSITIVITY["normal"]["battle_ms"]
    assert SENSITIVITY["hype"]["battle_ms"] < SENSITIVITY["normal"]["battle_ms"]
