"""Pure policy for OBS instant replay triggers (no IO)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Keep in sync with adapters/telemetry/domain_events.HOT_MOMENT_KINDS
DEFAULT_HOT_KINDS = frozenset(
    {"incident", "loss_of_control", "near_miss", "hard_overtake"}
)


@dataclass(frozen=True)
class InstantReplayConfig:
    enabled: bool = True
    cooldown_ms: int = 50_000
    max_play_ms: int = 10_000
    media_source_name: str = "Instant Replay Clip"
    scene_item_name: str = "Instant Replay"
    race_scenes: frozenset[str] = field(
        default_factory=lambda: frozenset({"Live", "Headcam"})
    )
    hot_kinds: frozenset[str] = field(default_factory=lambda: frozenset(DEFAULT_HOT_KINDS))


@dataclass
class InstantReplayDecision:
    """Result of evaluating a telemetry.event against policy."""

    trigger: bool
    reason: str
    kind: str | None = None
    event_id: str | None = None


class InstantReplayPolicy:
    """Cooldown + race-scene gate for hot-moment replays."""

    def __init__(self, cfg: InstantReplayConfig | None = None) -> None:
        self.cfg = cfg or InstantReplayConfig()
        self._last_trigger_ms = -10**12
        self._playing = False

    def reset(self) -> None:
        self._last_trigger_ms = -10**12
        self._playing = False

    def note_playing(self, playing: bool) -> None:
        self._playing = playing

    def evaluate(
        self,
        event: dict[str, Any],
        *,
        current_scene: str | None,
        now_ms: int,
    ) -> InstantReplayDecision:
        if not self.cfg.enabled:
            return InstantReplayDecision(False, "disabled")
        kind = str(event.get("kind") or "")
        if kind not in self.cfg.hot_kinds:
            return InstantReplayDecision(False, "not_hot", kind=kind or None)
        if self._playing:
            return InstantReplayDecision(False, "already_playing", kind=kind)
        scene = (current_scene or "").strip()
        if scene not in self.cfg.race_scenes:
            return InstantReplayDecision(False, "wrong_scene", kind=kind)
        if (now_ms - self._last_trigger_ms) < self.cfg.cooldown_ms:
            return InstantReplayDecision(False, "cooldown", kind=kind)
        eid = event.get("eventId")
        return InstantReplayDecision(
            True,
            "ok",
            kind=kind,
            event_id=str(eid) if eid is not None else None,
        )

    def mark_triggered(self, now_ms: int) -> None:
        self._last_trigger_ms = now_ms
        self._playing = True

    def mark_finished(self) -> None:
        self._playing = False


def instant_replay_config_from_dict(raw: dict[str, Any] | None) -> InstantReplayConfig:
    """Parse config.instantReplay object (missing → sensible defaults)."""
    data = raw if isinstance(raw, dict) else {}
    race = data.get("sceneItemScenes") or data.get("raceScenes")
    if isinstance(race, list) and race:
        race_set = frozenset(str(x) for x in race)
    else:
        race_set = frozenset({"Live", "Headcam"})
    kinds = data.get("hotKinds")
    if isinstance(kinds, list) and kinds:
        hot = frozenset(str(x) for x in kinds)
    else:
        hot = frozenset(DEFAULT_HOT_KINDS)
    return InstantReplayConfig(
        enabled=bool(data.get("enabled", True)),
        cooldown_ms=int(data.get("cooldownMs") or 50_000),
        max_play_ms=int(data.get("maxPlayMs") or 10_000),
        media_source_name=str(data.get("mediaSourceName") or "Instant Replay Clip"),
        scene_item_name=str(data.get("sceneItemName") or "Instant Replay"),
        race_scenes=race_set,
        hot_kinds=hot,
    )
