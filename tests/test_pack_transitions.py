"""Pack transition defaults (no OBS)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import generate_pack as gp  # noqa: E402


def test_marcato_default_is_move_650():
    overlays = ROOT / "overlays-marcato"
    transitions, current, duration = gp.build_transitions(
        overlays_dir=overlays, profile="marcato"
    )
    assert current == "S.Marcato Move"
    assert duration == 650
    names = [t["name"] for t in transitions]
    assert "Dissolvenza" in names
    assert "S.Marcato Stinger" in names
    assert "S.Marcato Move" in names
    stinger = next(t for t in transitions if t["name"] == "S.Marcato Stinger")
    assert stinger["settings"]["audio_fade_style"] == 1
    assert stinger["volume"] <= 0.55


def test_marcato_collections_lead_with_the_default_transition():
    """Quick-transition slot 1 must match the collection default in every profile file."""
    for filename in ("S_Marcato_42.json", "S_Marcato_Replay.json"):
        data = json.loads((ROOT / "obs" / filename).read_text(encoding="utf-8"))
        assert data["current_transition"] == "S.Marcato Move", filename
        assert data["transition_duration"] == 650, filename
        quick = data["quick_transitions"]
        assert quick[0]["name"] == data["current_transition"], filename
        assert quick[0]["duration"] == data["transition_duration"], filename
        assert "Dissolvenza" in [q["name"] for q in quick], filename


def test_apply_scene_transition_override_sets_private_settings():
    scene = gp.make_scene("Live", [])
    gp.apply_scene_transition_override(
        scene, transition_name="S.Marcato Stinger", duration_ms=850
    )
    assert scene["private_settings"]["transition"] == "S.Marcato Stinger"
    assert scene["private_settings"]["transition_duration"] == 850


def test_override_helper_idempotent():
    scene = gp.make_scene("Ending", [])
    gp.apply_scene_transition_override(
        scene, transition_name="S.Marcato Stinger", duration_ms=850
    )
    gp.apply_scene_transition_override(
        scene, transition_name="S.Marcato Stinger", duration_ms=850
    )
    assert scene["private_settings"]["transition"] == "S.Marcato Stinger"
    assert scene["private_settings"]["transition_duration"] == 850
