"""Pure OBS flag → scene mapping (no IO)."""

from __future__ import annotations

from dataclasses import dataclass, field


FLAG_SCENES = frozenset({"yellow", "red", "checkered"})
HOME_FLAGS = frozenset({"green", "none"})


@dataclass
class FlagDirectorConfig:
    scenes: dict[str, str]
    home_scene: str
    debounce_ms: int = 1500


@dataclass
class FlagDirector:
    config: FlagDirectorConfig
    _last_change_ms: int = field(default=-10**12, repr=False)
    _current_flag: str = field(default="green", repr=False)
    _active_scene: str | None = field(default=None, repr=False)
    _stacked_home: str | None = field(default=None, repr=False)

    def on_flag(self, flag: str, *, now_ms: int) -> str | None:
        """Return OBS scene name to switch to, or None if no action."""
        f = (flag or "none").strip().lower()
        if f == self._current_flag:
            return None
        if (now_ms - self._last_change_ms) < self.config.debounce_ms:
            return None

        target: str | None = None
        if f in FLAG_SCENES:
            target = self.config.scenes.get(f)
            if not target:
                return None
            if self._active_scene not in self.config.scenes.values():
                # Leaving a non-flag (or unknown) scene — remember home.
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
            # blue/white/etc. — no scene change in v1
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
