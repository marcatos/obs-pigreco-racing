"""Pack transition defaults (no OBS)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import generate_pack as gp  # noqa: E402


def test_marcato_default_is_dissolvenza_900():
    overlays = ROOT / "overlays-marcato"
    transitions, current, duration = gp.build_transitions(
        overlays_dir=overlays, profile="marcato"
    )
    assert current == "Dissolvenza"
    assert duration == 900
    names = [t["name"] for t in transitions]
    assert "Dissolvenza" in names
    assert "S.Marcato Stinger" in names
    assert "S.Marcato Move" in names
    stinger = next(t for t in transitions if t["name"] == "S.Marcato Stinger")
    assert stinger["settings"]["audio_fade_style"] == 1
    assert stinger["volume"] <= 0.55


def test_apply_scene_transition_override_sets_private_settings():
    scene = gp.make_scene("Live", [])
    gp.apply_scene_transition_override(
        scene, transition_name="S.Marcato Stinger", duration_ms=850
    )
    assert scene["private_settings"]["transition"] == "S.Marcato Stinger"
    assert scene["private_settings"]["transition_duration"] == 850
