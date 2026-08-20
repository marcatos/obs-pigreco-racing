# tests/test_instant_replay_policy.py
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "obs_flag_director"))

from domain_instant_replay import (
    InstantReplayConfig,
    InstantReplayPolicy,
    instant_replay_config_from_dict,
)


def test_triggers_on_hot_kind_in_live():
    p = InstantReplayPolicy()
    d = p.evaluate(
        {"kind": "incident", "eventId": "evt-1"},
        current_scene="Live",
        now_ms=1000,
    )
    assert d.trigger is True
    assert d.reason == "ok"
    p.mark_triggered(1000)
    d2 = p.evaluate(
        {"kind": "near_miss", "eventId": "evt-2"},
        current_scene="Live",
        now_ms=2000,
    )
    assert d2.trigger is False
    assert d2.reason == "already_playing"


def test_cooldown_blocks_spam():
    p = InstantReplayPolicy(InstantReplayConfig(cooldown_ms=50_000))
    p.mark_triggered(1000)
    p.mark_finished()
    d = p.evaluate(
        {"kind": "hard_overtake"},
        current_scene="Headcam",
        now_ms=20_000,
    )
    assert d.trigger is False
    assert d.reason == "cooldown"
    d2 = p.evaluate(
        {"kind": "hard_overtake"},
        current_scene="Headcam",
        now_ms=60_000,
    )
    assert d2.trigger is True


def test_wrong_scene_and_non_hot():
    p = InstantReplayPolicy()
    assert (
        p.evaluate({"kind": "incident"}, current_scene="Lobby", now_ms=1).reason
        == "wrong_scene"
    )
    assert (
        p.evaluate({"kind": "battle"}, current_scene="Live", now_ms=1).reason
        == "not_hot"
    )


def test_config_from_dict():
    cfg = instant_replay_config_from_dict(
        {
            "enabled": False,
            "cooldownMs": 12_000,
            "hotKinds": ["incident"],
            "sceneItemScenes": ["Live"],
        }
    )
    assert cfg.enabled is False
    assert cfg.cooldown_ms == 12_000
    assert cfg.hot_kinds == frozenset({"incident"})
    assert cfg.race_scenes == frozenset({"Live"})
