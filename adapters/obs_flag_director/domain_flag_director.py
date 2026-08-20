"""Pure OBS session + flag → scene mapping (no IO).

Extends P3-04 with Live ↔ Lobby. Default flag UX is transparent overlay FX
on Live (no full-screen color cutaways). Optional ``scenes`` presentation
still supports aux Flag * scenes that keep gameplay underneath.
"""

from __future__ import annotations

from dataclasses import dataclass, field


FLAG_SCENES = frozenset({"yellow", "red", "checkered"})
HOME_FLAGS = frozenset({"green", "none"})
DEFAULT_MANUAL_SCENES = frozenset({"Starting Soon", "BRB", "Ending"})
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

    def __post_init__(self) -> None:
        self.flags = FlagDirector(self.config.as_flag_config())

    def note_obs_scene(self, scene_name: str | None) -> None:
        self.flags.note_obs_scene(scene_name)

    def on_flag(self, flag: str, *, now_ms: int) -> str | None:
        scene = self.flags.on_flag(flag, now_ms=now_ms)
        if scene and scene in self.config.scenes.values():
            # Leaving Live/Lobby for a flag — keep preferred home by telem state
            preferred = self._preferred_home()
            self.flags.set_stacked_home(preferred)
        return scene

    def _preferred_home(self) -> str:
        if self._telem_connected:
            return self.config.live_scene
        # UI only or sim fully closed → Lobby (not Live)
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
        """Return Live/Lobby scene to switch to, or None.

        Does not leave Starting Soon / BRB / Ending or Flag scenes.
        """
        self._iracing_up = iracing_up
        self._telem_connected = telemetry_connected

        preferred = self._preferred_home()
        self.flags.set_stacked_home(preferred)

        if self._on_manual_scene() or self._on_flag_scene():
            return None

        if telemetry_connected:
            target = self.config.live_scene
        elif iracing_up:
            target = self.config.lobby_scene
        else:
            # Sim fully closed → Lobby (Starting Soon/BRB/Ending still protected above)
            target = self.config.lobby_scene

        if target == self.flags.active_scene:
            return None

        if (now_ms - self._last_session_change_ms) < self.config.session_debounce_ms:
            return None

        self._last_session_change_ms = now_ms
        self.flags.note_obs_scene(target)
        return target
