"""Unit tests for flag + session director domain (no OBS)."""

from __future__ import annotations

import asyncio
import logging
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
import director as runtime_director  # noqa: E402


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
            manual_scenes=frozenset(
                {"Starting Soon", "BRB", "Ending", "Reset Session"}
            ),
            reset_session_scene="Reset Session",
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


def test_session_iracing_closed_goes_lobby():
    s = _session()
    s.note_obs_scene("Live")
    assert (
        s.on_session_state(iracing_up=False, telemetry_connected=False, now_ms=5000)
        == "Lobby"
    )


def test_session_headcam_closed_goes_lobby_then_restores_headcam():
    s = _session()
    s.note_obs_scene("Headcam")
    assert (
        s.on_session_state(iracing_up=False, telemetry_connected=False, now_ms=5000)
        == "Lobby"
    )
    assert s._resume_scene == "Headcam"
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=10000)
        == "Headcam"
    )


def test_session_telem_up_does_not_yank_headcam():
    s = _session()
    s.note_obs_scene("Headcam")
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=5000) is None
    )
    assert s.flags.active_scene == "Headcam"


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


def test_reset_session_restores_live_from_live():
    s = _session()
    s.note_obs_scene("Live")
    assert s.on_reset_session_scene(previous_scene="Live") == "Live"


def test_reset_session_restores_headcam():
    s = _session()
    s.note_obs_scene("Headcam")
    assert s.on_reset_session_scene(previous_scene="Headcam") == "Headcam"


def test_reset_session_stays_on_starting_soon():
    s = _session()
    s.note_obs_scene("Starting Soon")
    assert s.on_reset_session_scene(previous_scene="Starting Soon") is None


def test_reset_session_without_previous_falls_back_to_lobby():
    s = _session()
    assert s.on_reset_session_scene(previous_scene=None) == "Lobby"
    assert s.preferred_home_scene() == "Lobby"


def test_reset_session_without_previous_falls_back_to_live_when_telemetry_up():
    s = _session()
    s.note_obs_scene("Live")
    s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=1000)
    assert s.on_reset_session_scene(previous_scene=None) == "Live"
    assert s.on_reset_session_scene(previous_scene="") == "Live"


def test_reset_session_scene_is_manual():
    s = _session()
    s.note_obs_scene("Reset Session")
    assert (
        s.on_session_state(iracing_up=True, telemetry_connected=True, now_ms=5000)
        is None
    )


def test_build_session_director_defaults_reset_scene_to_manual():
    s = runtime_director.build_session_director({})
    assert s.config.reset_session_scene == "Reset Session"
    assert "Reset Session" in s.config.manual_scenes


def test_session_reset_command_shape():
    assert runtime_director.session_reset_command(now_ms=1234) == {
        "type": "telemetry.command",
        "schemaVersion": 1,
        "ts": 1234,
        "command": "session_reset",
        "reason": "manual",
    }


def test_offline_session_reset_is_not_queued(caplog):
    command_q: asyncio.Queue[dict[str, object]] = asyncio.Queue()

    with caplog.at_level(logging.WARNING, logger="pigreco.session_director"):
        queued = runtime_director.queue_session_reset(
            command_q,
            telemetry_connected=False,
            now_ms=1234,
        )

    assert queued is False
    assert command_q.empty()
    assert "local clear only" in caplog.text


def test_connected_session_reset_is_queued():
    command_q: asyncio.Queue[dict[str, object]] = asyncio.Queue()

    queued = runtime_director.queue_session_reset(
        command_q,
        telemetry_connected=True,
        now_ms=1234,
    )

    assert queued is True
    assert command_q.get_nowait() == runtime_director.session_reset_command(now_ms=1234)


def test_disconnect_discards_queued_session_reset(caplog):
    command_q: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    command_q.put_nowait(runtime_director.session_reset_command(now_ms=1234))

    with caplog.at_level(logging.WARNING, logger="pigreco.session_director"):
        dropped = runtime_director.discard_pending_commands(
            command_q,
            reason="telemetry_disconnect",
        )

    assert dropped == 1
    assert command_q.empty()
    assert "dropped=1" in caplog.text


class _ReplayObs:
    def __init__(self) -> None:
        self.item_enabled: list[tuple[str, str, bool]] = []

    def set_scene_item_enabled(
        self, scene_name: str, source_name: str, enabled: bool
    ) -> bool:
        self.item_enabled.append((scene_name, source_name, enabled))
        return True


def test_local_session_reset_clears_replay_and_hides_clip():
    obs = _ReplayObs()
    replay = runtime_director.InstantReplayController(
        obs,  # type: ignore[arg-type]
        {"instantReplay": {"sceneItemScenes": ["Live"]}},
    )
    replay.policy.mark_triggered(1000)

    asyncio.run(replay.reset_local(previous_scene="Live"))

    assert obs.item_enabled == [("Live", "Instant Replay", False)]
    assert replay.policy.evaluate(
        {"kind": "incident"}, current_scene="Live", now_ms=1001
    ).trigger
