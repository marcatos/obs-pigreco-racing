"""Unit tests for flag + session director domain (no OBS)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "obs_flag_director"))

from domain_flag_director import (  # noqa: E402
    FlagDirector,
    FlagDirectorConfig,
    SessionDirector,
    SessionDirectorConfig,
)


def _dir(**kw) -> FlagDirector:
    cfg = FlagDirectorConfig(
        scenes={
            "yellow": "Flag Yellow",
            "red": "Flag Red",
            "checkered": "Flag Checkered",
        },
        home_scene="Rec * Live",
        debounce_ms=1500,
        presentation=kw.get("presentation", "scenes"),
    )
    return FlagDirector(cfg)


def _session(**kw) -> SessionDirector:
    return SessionDirector(
        SessionDirectorConfig(
            scenes={
                "yellow": "Flag Yellow",
                "red": "Flag Red",
                "checkered": "Flag Checkered",
            },
            live_scene="Live",
            lobby_scene="Lobby",
            home_scene="Live",
            flag_debounce_ms=1500,
            session_debounce_ms=4000,
            flag_presentation=kw.get("flag_presentation", "scenes"),
        )
    )


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
        FlagDirectorConfig(
            scenes={"yellow": "Flag Yellow"},
            home_scene="Home",
            debounce_ms=0,
            presentation="scenes",
        )
    )
    assert d.on_flag("red", now_ms=1) is None


def test_overlay_presentation_never_switches_scene():
    d = _dir(presentation="overlay")
    d.note_obs_scene("Live")
    assert d.on_flag("yellow", now_ms=1000) is None
    assert d.on_flag("red", now_ms=3000) is None
    assert d.on_flag("checkered", now_ms=5000) is None
    assert d.on_flag("green", now_ms=7000) is None
    assert d.active_scene == "Live"


def test_overlay_still_debounces():
    d = _dir(presentation="overlay")
    assert d.on_flag("yellow", now_ms=1000) is None
    assert d.on_flag("red", now_ms=1100) is None  # debounce
    assert d.on_flag("red", now_ms=3000) is None


def test_session_telem_up_goes_live():
    s = _session()
    s.note_obs_scene("Lobby")
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=5000) == "Live"
    )


def test_session_iracing_no_telem_goes_lobby():
    s = _session()
    s.note_obs_scene("Live")
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=False, now_ms=5000)
        == "Lobby"
    )


def test_session_debounce():
    s = _session()
    s.note_obs_scene("Lobby")
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=1000) == "Live"
    )
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=False, now_ms=2000) is None
    )
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=False, now_ms=6000)
        == "Lobby"
    )


def test_session_ignores_starting_soon():
    s = _session()
    s.note_obs_scene("Starting Soon")
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=5000) is None
    )


def test_session_ignores_flag_scene():
    s = _session()
    s.note_obs_scene("Flag Yellow")
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=5000) is None
    )


def test_session_flag_then_green_returns_live():
    s = _session()
    s.note_obs_scene("Live")
    s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=1000)
    assert s.on_flag("yellow", now_ms=2000) == "Flag Yellow"
    assert s.on_flag("green", now_ms=4000) == "Live"


def test_session_overlay_flag_stays_on_live():
    s = _session(flag_presentation="overlay")
    s.note_obs_scene("Live")
    s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=1000)
    assert s.on_flag("yellow", now_ms=2000) is None
    assert s.on_flag("green", now_ms=4000) is None
    assert s.flags.active_scene == "Live"
    # Live↔Lobby still works
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=False, now_ms=8000)
        == "Lobby"
    )
