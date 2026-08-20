"""Pure OBS session + flag → scene mapping (no IO).

Extends P3-04 with Live ↔ Lobby. Default flag UX is transparent overlay FX
on Live (no full-screen color cutaways). Optional ``scenes`` presentation
still supports aux Flag * scenes that keep gameplay underneath.
"""

from __future__ import annotations

from dataclasses import dataclass, field


FLAG_SCENES = frozenset({"yellow", "red", "checkered"})
HOME_FLAGS = frozenset({"green", "none"})
DEFAULT_MANUAL_SCENES = frozenset(
    {"Starting Soon", "BRB", "Ending", "Reset Session"}
)
# overlay = Browser Source FX on Live (recommended); scenes = OBS program cuts
PRESENTATIONS = frozenset({"overlay", "scenes"})


@dataclass
class FlagDirectorConfig:
    scenes: dict[str, str]
    home_scene: str
    debounce_ms: int = 1500
    presentation: str = "overlay"


@dataclass
class SessionDirectorConfig:
    """Flag handling + live/lobby session automation."""

    scenes: dict[str, str]
    live_scene: str = "Live"
    lobby_scene: str = "Lobby"
    home_scene: str = "Live"
    flag_debounce_ms: int = 1500
    session_debounce_ms: int = 4000
    flag_presentation: str = "overlay"
    manual_scenes: frozenset[str] = field(default_factory=lambda: DEFAULT_MANUAL_SCENES)
    reset_session_scene: str = "Reset Session"
    # Scenes the operator may stay on during a race; resume after Lobby.
    race_scenes: frozenset[str] = field(
        default_factory=lambda: frozenset({"Live", "Headcam"})
    )

    def as_flag_config(self) -> FlagDirectorConfig:
        return FlagDirectorConfig(
            scenes=dict(self.scenes),
            home_scene=self.home_scene,
            debounce_ms=self.flag_debounce_ms,
            presentation=self.flag_presentation,
        )


@dataclass
class FlagDirector:
    config: FlagDirectorConfig
    _last_change_ms: int = field(default=-10**12, repr=False)
    _current_flag: str = field(default="green", repr=False)
    _active_scene: str | None = field(default=None, repr=False)
    _stacked_home: str | None = field(default=None, repr=False)

    def on_flag(self, flag: str, *, now_ms: int) -> str | None:
        """Return OBS scene name to switch to, or None if no action.

        With ``presentation="overlay"`` never requests a scene change — the
        Live Browser Source listens to telemetry and animates in place.
        """
        f = (flag or "none").strip().lower()
        if f == self._current_flag:
            return None
        if (now_ms - self._last_change_ms) < self.config.debounce_ms:
            return None

        if self.config.presentation == "overlay":
            # Track flag for debounce / logging; FX overlay handles visuals.
            if f in FLAG_SCENES or f in HOME_FLAGS or f:
                self._current_flag = f
                self._last_change_ms = now_ms
            return None

        target: str | None = None
        if f in FLAG_SCENES:
            target = self.config.scenes.get(f)
            if not target:
                return None
            if self._active_scene not in self.config.scenes.values():
                if self._active_scene:
                    self._stacked_home = self._active_scene
                elif not self._stacked_home:
                    self._stacked_home = self.config.home_scene
            if target == self._active_scene:
                self._current_flag = f
                self._last_change_ms = now_ms
                return None
        elif f in HOME_FLAGS:
            target = self._stacked_home or self.config.home_scene
            if target == self._active_scene:
                self._current_flag = f
                self._last_change_ms = now_ms
                return None
        else:
            self._current_flag = f
            self._last_change_ms = now_ms
            return None

        self._current_flag = f
        self._last_change_ms = now_ms
        self._active_scene = target
        return target

    def note_obs_scene(self, scene_name: str | None) -> None:
        """Optional: sync from OBS current program scene."""
        if scene_name:
            self._active_scene = scene_name
            if scene_name not in self.config.scenes.values():
                self._stacked_home = scene_name

    @property
    def active_scene(self) -> str | None:
        return self._active_scene

    @property
    def stacked_home(self) -> str | None:
        return self._stacked_home

    def set_stacked_home(self, scene: str) -> None:
        self._stacked_home = scene


@dataclass
class SessionDirector:
    """Flag cuts + Live/Lobby from telemetry connected state."""

    config: SessionDirectorConfig
    flags: FlagDirector = field(init=False)
    _last_session_change_ms: int = field(default=-10**12, repr=False)
    _telem_connected: bool | None = field(default=None, repr=False)
    _iracing_up: bool = field(default=False, repr=False)
    # Last Live/Headcam (or other race scene) before Lobby — restored on telem up.
    _resume_scene: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.flags = FlagDirector(self.config.as_flag_config())

    def note_obs_scene(self, scene_name: str | None) -> None:
        self.flags.note_obs_scene(scene_name)
        if scene_name and scene_name in self.config.race_scenes:
            self._resume_scene = scene_name

    def on_flag(self, flag: str, *, now_ms: int) -> str | None:
        scene = self.flags.on_flag(flag, now_ms=now_ms)
        if scene and scene in self.config.scenes.values():
            preferred = self._preferred_home()
            self.flags.set_stacked_home(preferred)
        return scene

    def on_reset_session_scene(self, *, previous_scene: str | None) -> str | None:
        """Return the scene to restore after a manual reset.

        A prior race scene comes back as-is. An unknown previous scene falls
        back to the preferred home so program never strands on the empty Reset
        Session scene. Other known scenes (Starting Soon, BRB, …) return None:
        the caller keeps the operator where they were.
        """
        previous = (previous_scene or "").strip()
        if previous in self.config.race_scenes:
            return previous
        if not previous:
            return self._preferred_home()
        return None

    def preferred_home_scene(self) -> str:
        """Last-resort target for callers that must leave a placeholder scene."""
        return self._preferred_home()

    def _preferred_home(self) -> str:
        if self._telem_connected:
            return self._resume_scene or self.config.live_scene
        return self.config.lobby_scene

    def _on_manual_scene(self) -> bool:
        cur = self.flags.active_scene
        return bool(cur and cur in self.config.manual_scenes)

    def _on_flag_scene(self) -> bool:
        cur = self.flags.active_scene
        return bool(cur and cur in self.config.scenes.values())

    def on_session_state(
        self,
        *,
        iracing_up: bool,
        telemetry_connected: bool,
        now_ms: int,
    ) -> str | None:
        """Return scene to switch to, or None.

        - No telem (UI only or iRacing closed) → Lobby from Live/Headcam.
        - Telem up → restore last race scene (Live or Headcam); do not yank
          Headcam→Live while the operator is already on a race scene.
        - Never leaves Starting Soon / BRB / Ending or Flag scenes.
        """
        self._iracing_up = iracing_up
        self._telem_connected = telemetry_connected

        cur = self.flags.active_scene
        if cur and cur in self.config.race_scenes:
            self._resume_scene = cur

        preferred = self._preferred_home()
        self.flags.set_stacked_home(preferred)

        if self._on_manual_scene() or self._on_flag_scene():
            return None

        if telemetry_connected:
            if cur in self.config.race_scenes:
                return None
            target = self._resume_scene or self.config.live_scene
        else:
            # UI-only or fully closed → Lobby (manual scenes already protected)
            target = self.config.lobby_scene

        if target == cur:
            return None

        if (now_ms - self._last_session_change_ms) < self.config.session_debounce_ms:
            return None

        self._last_session_change_ms = now_ms
        self.flags.note_obs_scene(target)
        return target
