#!/usr/bin/env python3
"""
Session Director (P3-04 + Live↔Lobby).

Listens to PiGreco telemetry WebSocket, watches iRacing processes, optionally
starts the telemetry bridge, and switches OBS scenes:
  - flagPresentation=overlay (default): yellow/red/checkered stay on Live;
    Overlay Flag FX animates from telemetry (no flat color cutaways)
  - flagPresentation=scenes: yellow/red/checkered → Flag * aux scenes
  - telemetry connected → Live
  - iRacing up without telemetry → Lobby
  - never auto-leaves Starting Soon / BRB / Ending

Usage:
  copy config.example.json → config.local.json
  python adapters/obs_flag_director/director.py
  python adapters/obs_flag_director/director.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from domain_flag_director import (  # noqa: E402
    DEFAULT_MANUAL_SCENES,
    FlagDirector,
    FlagDirectorConfig,
    SessionDirector,
    SessionDirectorConfig,
)
from domain_instant_replay import (  # noqa: E402
    InstantReplayPolicy,
    instant_replay_config_from_dict,
)

log = logging.getLogger("pigreco.session_director")

DEFAULT_CONFIG = HERE / "config.local.json"
EXAMPLE_CONFIG = HERE / "config.example.json"


def _hidden_run_kwargs() -> dict[str, Any]:
    """Avoid flashing cmd/PowerShell consoles on every Session Director poll."""
    if sys.platform != "win32":
        return {}
    # CREATE_NO_WINDOW — tasklist/netstat otherwise pop a console ~1 Hz
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}


def _detached_spawn_flags() -> int:
    if sys.platform != "win32":
        return 0
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    return 0x00000008 | 0x00000200 | 0x08000000


def _ms_now() -> int:
    return int(time.time() * 1000)


def session_reset_command(*, now_ms: int) -> dict[str, Any]:
    """Build the telemetry bridge command for a manual session reset."""
    return {
        "type": "telemetry.command",
        "schemaVersion": 1,
        "ts": now_ms,
        "command": "session_reset",
        "reason": "manual",
    }


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Copy {EXAMPLE_CONFIG.name} to config.local.json"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return data


def _flag_presentation(cfg: dict[str, Any]) -> str:
    raw = str(cfg.get("flagPresentation") or "overlay").strip().lower()
    return raw if raw in ("overlay", "scenes") else "overlay"


def build_flag_director(cfg: dict[str, Any]) -> FlagDirector:
    """Backward-compatible flag-only director (tests / legacy)."""
    scenes = cfg.get("scenes") or {}
    if not isinstance(scenes, dict):
        scenes = {}
    return FlagDirector(
        FlagDirectorConfig(
            scenes={str(k).lower(): str(v) for k, v in scenes.items()},
            home_scene=str(cfg.get("homeScene") or "Live"),
            debounce_ms=int(cfg.get("debounceMs") or 1500),
            presentation=_flag_presentation(cfg),
        )
    )


def build_session_director(cfg: dict[str, Any]) -> SessionDirector:
    scenes = cfg.get("scenes") or {}
    if not isinstance(scenes, dict):
        scenes = {}
    reset_scene = str(cfg.get("resetSessionScene") or "Reset Session")
    manual = cfg.get("manualScenes")
    configured_manual = (
        frozenset(str(x) for x in manual if str(x).strip())
        if isinstance(manual, list)
        else DEFAULT_MANUAL_SCENES
    )
    manual_set = configured_manual | {reset_scene}
    race = cfg.get("raceScenes")
    race_set = (
        frozenset(str(x) for x in race)
        if isinstance(race, list) and race
        else frozenset({"Live", "Headcam"})
    )
    return SessionDirector(
        SessionDirectorConfig(
            scenes={str(k).lower(): str(v) for k, v in scenes.items()},
            live_scene=str(cfg.get("liveScene") or "Live"),
            lobby_scene=str(cfg.get("lobbyScene") or "Lobby"),
            home_scene=str(cfg.get("homeScene") or cfg.get("liveScene") or "Live"),
            flag_debounce_ms=int(cfg.get("debounceMs") or 1500),
            session_debounce_ms=int(cfg.get("sessionDebounceMs") or 4000),
            flag_presentation=_flag_presentation(cfg),
            manual_scenes=manual_set,
            reset_session_scene=reset_scene,
            race_scenes=race_set,
        )
    )


# Alias used by older imports / Start-FlagDirector
build_director = build_flag_director


class ObsScenePort:
    """Port for switching program scene (dry-run or real OBS)."""

    def set_scene(self, name: str) -> None:
        raise NotImplementedError

    def get_current_scene(self) -> str | None:
        return None

    def save_replay_buffer(self) -> bool:
        return False

    def get_last_replay_path(self) -> str | None:
        return None

    def set_media_local_file(self, source_name: str, path: str) -> bool:
        return False

    def set_scene_item_enabled(
        self, scene_name: str, source_name: str, enabled: bool
    ) -> bool:
        return False

    def restart_media(self, source_name: str) -> bool:
        return False

    def close(self) -> None:
        return None


class DryRunObs(ObsScenePort):
    def __init__(self) -> None:
        self.last: str | None = "Live"
        self.last_replay_path: str | None = None
        self.media_files: dict[str, str] = {}
        self.item_enabled: dict[tuple[str, str], bool] = {}

    def set_scene(self, name: str) -> None:
        self.last = name
        log.info("DRY-RUN set_scene name=%s", name)

    def get_current_scene(self) -> str | None:
        return self.last

    def save_replay_buffer(self) -> bool:
        self.last_replay_path = str(ROOT / "replays" / "dry-run-replay.mp4")
        log.info("DRY-RUN save_replay_buffer → %s", self.last_replay_path)
        return True

    def get_last_replay_path(self) -> str | None:
        return self.last_replay_path

    def set_media_local_file(self, source_name: str, path: str) -> bool:
        self.media_files[source_name] = path
        log.info("DRY-RUN set_media_local_file source=%s path=%s", source_name, path)
        return True

    def set_scene_item_enabled(
        self, scene_name: str, source_name: str, enabled: bool
    ) -> bool:
        self.item_enabled[(scene_name, source_name)] = enabled
        log.info(
            "DRY-RUN set_scene_item_enabled scene=%s source=%s enabled=%s",
            scene_name,
            source_name,
            enabled,
        )
        return True

    def restart_media(self, source_name: str) -> bool:
        log.info("DRY-RUN restart_media source=%s", source_name)
        return True


class LiveObs(ObsScenePort):
    def __init__(self, host: str, port: int, password: str) -> None:
        from obsws_python import ReqClient  # type: ignore

        self._client = ReqClient(host=host, port=port, password=password, timeout=5)
        self._item_id_cache: dict[tuple[str, str], int] = {}

    def set_scene(self, name: str) -> None:
        self._client.set_current_program_scene(name)
        log.info("OBS set_current_program_scene name=%s", name)

    def get_current_scene(self) -> str | None:
        try:
            resp = self._client.get_current_program_scene()
            return getattr(resp, "current_program_scene_name", None)
        except Exception as exc:  # noqa: BLE001
            log.warning("OBS get_current_scene failed: %s", exc)
            return None

    def save_replay_buffer(self) -> bool:
        try:
            # Ensure buffer is active (no-op if already started).
            try:
                status = self._client.get_replay_buffer_status()
                active = bool(getattr(status, "output_active", False))
                if not active:
                    self._client.start_replay_buffer()
                    log.info("OBS start_replay_buffer")
            except Exception as exc:  # noqa: BLE001
                log.debug("OBS replay buffer status/start: %s", exc)
            self._client.save_replay_buffer()
            log.info("OBS save_replay_buffer")
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("OBS save_replay_buffer failed: %s", exc)
            return False

    def get_last_replay_path(self) -> str | None:
        try:
            resp = self._client.get_last_replay_buffer_replay()
            path = getattr(resp, "saved_replay_path", None)
            if path:
                return str(path)
            return None
        except Exception as exc:  # noqa: BLE001
            log.warning("OBS get_last_replay_buffer_replay failed: %s", exc)
            return None

    def set_media_local_file(self, source_name: str, path: str) -> bool:
        try:
            self._client.set_input_settings(
                source_name,
                {"local_file": path, "is_local_file": True},
                True,
            )
            log.info("OBS set_input_settings media source=%s", source_name)
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("OBS set_media_local_file failed: %s", exc)
            return False

    def _scene_item_id(self, scene_name: str, source_name: str) -> int | None:
        key = (scene_name, source_name)
        if key in self._item_id_cache:
            return self._item_id_cache[key]
        try:
            resp = self._client.get_scene_item_id(scene_name, source_name)
            item_id = int(getattr(resp, "scene_item_id"))
            self._item_id_cache[key] = item_id
            return item_id
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "OBS get_scene_item_id scene=%s source=%s failed: %s",
                scene_name,
                source_name,
                exc,
            )
            return None

    def set_scene_item_enabled(
        self, scene_name: str, source_name: str, enabled: bool
    ) -> bool:
        item_id = self._scene_item_id(scene_name, source_name)
        if item_id is None:
            return False
        try:
            self._client.set_scene_item_enabled(scene_name, item_id, enabled)
            log.info(
                "OBS set_scene_item_enabled scene=%s source=%s enabled=%s",
                scene_name,
                source_name,
                enabled,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("OBS set_scene_item_enabled failed: %s", exc)
            return False

    def restart_media(self, source_name: str) -> bool:
        try:
            # OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART = "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
            self._client.trigger_media_input_action(
                source_name, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
            )
            log.info("OBS restart_media source=%s", source_name)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("OBS restart_media failed: %s", exc)
            return False

    def close(self) -> None:
        return None


class InstantReplayController:
    """Orchestrates SaveReplayBuffer → show nested Instant Replay on current scene."""

    def __init__(self, obs: ObsScenePort, cfg: dict[str, Any]) -> None:
        raw_ir = cfg.get("instantReplay")
        merged: dict[str, Any] = dict(raw_ir) if isinstance(raw_ir, dict) else {}
        if "sceneItemScenes" not in merged and isinstance(cfg.get("raceScenes"), list):
            merged["sceneItemScenes"] = cfg["raceScenes"]
        ir_cfg = instant_replay_config_from_dict(merged)
        self.policy = InstantReplayPolicy(ir_cfg)
        self.obs = obs
        self._hide_task: asyncio.Task[None] | None = None
        self._active_scene: str | None = None
        log.info(
            "InstantReplay enabled=%s cooldownMs=%d maxPlayMs=%d scenes=%s kinds=%s",
            ir_cfg.enabled,
            ir_cfg.cooldown_ms,
            ir_cfg.max_play_ms,
            sorted(ir_cfg.race_scenes),
            sorted(ir_cfg.hot_kinds),
        )

    async def on_event(self, event: dict[str, Any], *, now_ms: int) -> None:
        t0 = time.perf_counter()
        scene = await asyncio.to_thread(self.obs.get_current_scene)
        decision = self.policy.evaluate(event, current_scene=scene, now_ms=now_ms)
        if not decision.trigger:
            log.debug(
                "InstantReplay skip reason=%s kind=%s scene=%s",
                decision.reason,
                decision.kind,
                scene,
            )
            return
        log.info(
            "InstantReplay trigger kind=%s eventId=%s scene=%s",
            decision.kind,
            decision.event_id,
            scene,
        )
        self.policy.mark_triggered(now_ms)
        ok = await asyncio.to_thread(self._play_on_scene, scene or "Live")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if not ok:
            self.policy.mark_finished()
            log.error("InstantReplay failed after %.0f ms", elapsed_ms)
            return
        self._active_scene = scene or "Live"
        log.info("InstantReplay shown in %.0f ms; scheduling hide", elapsed_ms)
        if self._hide_task and not self._hide_task.done():
            self._hide_task.cancel()
        self._hide_task = asyncio.create_task(
            self._hide_later(scene or "Live", self.policy.cfg.max_play_ms)
        )

    async def reset_local(self, *, previous_scene: str | None = None) -> None:
        """Clear replay cooldown/playing state and hide any visible replay."""
        started = time.perf_counter()
        if self._hide_task and not self._hide_task.done():
            self._hide_task.cancel()
            try:
                await self._hide_task
            except asyncio.CancelledError:
                pass
        self._hide_task = None

        hide_scene = self._active_scene
        previous = (previous_scene or "").strip()
        if hide_scene is None and previous in self.policy.cfg.race_scenes:
            hide_scene = previous
        self._active_scene = None
        self.policy.reset()

        hidden = False
        if hide_scene:
            hidden = await asyncio.to_thread(
                self.obs.set_scene_item_enabled,
                hide_scene,
                self.policy.cfg.scene_item_name,
                False,
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info(
            "Session reset local clear replayHidden=%s scene=%s durationMs=%.0f",
            hidden,
            hide_scene,
            elapsed_ms,
        )

    def _play_on_scene(self, scene_name: str) -> bool:
        cfg = self.policy.cfg
        if not self.obs.save_replay_buffer():
            return False
        # Brief wait for disk write (OBS async save).
        time.sleep(0.35)
        path = self.obs.get_last_replay_path()
        if not path:
            log.error("InstantReplay: no saved replay path")
            return False
        if not self.obs.set_media_local_file(cfg.media_source_name, path):
            return False
        self.obs.restart_media(cfg.media_source_name)
        if not self.obs.set_scene_item_enabled(scene_name, cfg.scene_item_name, True):
            return False
        return True

    async def _hide_later(self, scene_name: str, delay_ms: int) -> None:
        try:
            await asyncio.sleep(max(0.5, delay_ms / 1000.0))
            await asyncio.to_thread(
                self.obs.set_scene_item_enabled,
                scene_name,
                self.policy.cfg.scene_item_name,
                False,
            )
            log.info("InstantReplay hidden scene=%s", scene_name)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("InstantReplay hide failed: %s", exc)
        finally:
            self.policy.mark_finished()
            if self._active_scene == scene_name:
                self._active_scene = None


def connect_obs(cfg: dict[str, Any], *, force_dry: bool) -> ObsScenePort:
    if force_dry or cfg.get("dryRun") is True:
        log.info("Using dry-run OBS port (no websocket to OBS)")
        return DryRunObs()
    host = str(cfg.get("obsHost") or "127.0.0.1")
    port = int(cfg.get("obsPort") or 4455)
    password = str(cfg.get("obsPassword") or "")
    try:
        live = LiveObs(host, port, password)
        log.info("Connected to OBS websocket host=%s port=%d", host, port)
        return live
    except Exception as exc:  # noqa: BLE001
        log.error(
            "OBS connect failed (%s); falling back to dry-run. "
            "Install: pip install -r adapters/obs_flag_director/requirements.txt",
            type(exc).__name__,
        )
        return DryRunObs()


def apply_flag(
    director: FlagDirector | SessionDirector,
    obs: ObsScenePort,
    flag: str,
    *,
    now_ms: int | None = None,
) -> str | None:
    scene = director.on_flag(flag, now_ms=now_ms if now_ms is not None else _ms_now())
    if scene:
        obs.set_scene(scene)
    return scene


def process_running(names: list[str]) -> bool:
    """True if any of the given Windows process image names is running."""
    if not names:
        return False
    try:
        # tasklist is always available; avoid third-party deps
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            **_hidden_run_kwargs(),
        )
        if proc.returncode != 0:
            return False
        lower = proc.stdout.lower()
        return any(n.lower() in lower for n in names)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.debug("process_running failed: %s", exc)
        return False


def telemetry_port_open(host: str = "127.0.0.1", port: int = 8765) -> bool:
    """True if something is already listening on the telemetry WS port.

    Do **not** use a bare TCP connect: websockets then logs
    ``InvalidMessage: did not receive a valid HTTP request`` on every poll.
    """
    _ = host  # reserved for future host-specific bind checks
    try:
        out = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            **_hidden_run_kwargs(),
        ).stdout or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.debug("telemetry_port_open netstat failed: %s", exc)
        return False

    port_tok = f":{int(port)}"
    for line in out.splitlines():
        upper = line.upper()
        if "LISTENING" not in upper or "UDP" in upper:
            continue
        if port_tok in line:
            return True
    return False


class TelemetryLauncher:
    """Spawn Start-Telemetry once; cooldown to avoid spam."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.enabled = bool(cfg.get("autoStartTelemetry", True))
        self.mode = str(cfg.get("telemetryMode") or "iracing")
        self._last_start_ms = -10**12
        self._cooldown_ms = int(cfg.get("telemetryStartCooldownMs") or 30000)
        self._child: subprocess.Popen[str] | None = None

    def maybe_start(self, *, now_ms: int) -> None:
        if not self.enabled:
            return
        if telemetry_port_open():
            return
        if (now_ms - self._last_start_ms) < self._cooldown_ms:
            return
        bat = ROOT / "Start-Telemetry.bat"
        py = ROOT / "tools" / "start_telemetry.py"
        self._last_start_ms = now_ms
        flags = _detached_spawn_flags()
        try:
            # Prefer python (no console) over .bat which always flashes cmd.
            if py.is_file():
                log.info("Starting telemetry via start_telemetry.py %s", self.mode)
                self._child = subprocess.Popen(
                    [sys.executable, str(py), self.mode],
                    cwd=str(ROOT),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                    close_fds=True,
                )
            elif bat.is_file():
                log.info("Starting telemetry via %s %s", bat.name, self.mode)
                self._child = subprocess.Popen(
                    ["cmd", "/c", str(bat), self.mode],
                    cwd=str(ROOT),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                    close_fds=True,
                )
            else:
                log.error("No Start-Telemetry.bat or tools/start_telemetry.py found")
        except OSError as exc:
            log.error("Failed to start telemetry: %s", exc)


async def run_director_loop(
    cfg: dict[str, Any],
    director: SessionDirector,
    obs: ObsScenePort,
    stop: asyncio.Event,
) -> None:
    try:
        import websockets
    except ImportError as exc:
        raise SystemExit(
            "websockets required. pip install -r adapters/obs_flag_director/requirements.txt"
        ) from exc

    url = str(cfg.get("telemetryWsUrl") or "ws://127.0.0.1:8765")
    proc_names = cfg.get("iracingProcessNames") or [
        "iRacingSim64DX11.exe",
        "iRacingUI.exe",
    ]
    if not isinstance(proc_names, list):
        proc_names = ["iRacingSim64DX11.exe", "iRacingUI.exe"]
    proc_names = [str(x) for x in proc_names]

    launcher = TelemetryLauncher(cfg)
    last_tick_flag: str | None = None
    last_tick_ms = -10**12
    telem_connected = False
    tick_stale_ms = int(cfg.get("telemetryStaleMs") or 5000)
    poll_s = float(cfg.get("sessionPollSec") or 1.0)
    replay = InstantReplayController(obs, cfg)
    command_q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    reset_scene = director.config.reset_session_scene

    log.info("Session director loop url=%s processes=%s", url, proc_names)

    async def session_poll() -> None:
        nonlocal last_tick_flag, telem_connected
        previous_program_scene: str | None = None
        while not stop.is_set():
            now = _ms_now()
            iracing_up = await asyncio.to_thread(process_running, proc_names)
            if iracing_up:
                launcher.maybe_start(now_ms=now)

            # Stale ticks ⇒ treat as disconnected for Lobby switch
            if telem_connected and (now - last_tick_ms) > tick_stale_ms:
                log.info("Telemetry ticks stale > %d ms", tick_stale_ms)
                telem_connected = False

            cur = await asyncio.to_thread(obs.get_current_scene)
            if cur == reset_scene and previous_program_scene != reset_scene:
                previous = previous_program_scene
                await replay.reset_local(previous_scene=previous)
                last_tick_flag = None
                command_q.put_nowait(session_reset_command(now_ms=now))
                log.info(
                    "Reset Session scene entered previous=%s commandQueued=%d",
                    previous,
                    command_q.qsize(),
                )

                restore = director.on_reset_session_scene(previous_scene=previous)
                target = restore
                if target is None and previous and previous != reset_scene:
                    target = previous
                if target:
                    try:
                        await asyncio.to_thread(obs.set_scene, target)
                        director.note_obs_scene(target)
                        log.info("Reset Session restored scene=%s", target)
                    except Exception:  # noqa: BLE001
                        log.exception(
                            "Reset Session could not restore previous scene=%s",
                            target,
                        )
                else:
                    log.warning("Reset Session has no previous scene to restore")
                previous_program_scene = reset_scene
                try:
                    await asyncio.wait_for(stop.wait(), timeout=poll_s)
                except asyncio.TimeoutError:
                    pass
                continue

            if cur:
                director.note_obs_scene(cur)
                previous_program_scene = cur

            scene = director.on_session_state(
                iracing_up=iracing_up,
                telemetry_connected=telem_connected,
                now_ms=now,
            )
            if scene:
                obs.set_scene(scene)

            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_s)
            except asyncio.TimeoutError:
                pass

    async def command_sender(ws: Any) -> None:
        while not stop.is_set():
            command = await command_q.get()
            try:
                await ws.send(json.dumps(command, separators=(",", ":")))
                log.info(
                    "Telemetry command sent command=%s queued=%d",
                    command.get("command"),
                    command_q.qsize(),
                )
            except Exception:  # noqa: BLE001
                command_q.put_nowait(command)
                raise
            finally:
                command_q.task_done()

    async def ws_loop() -> None:
        nonlocal telem_connected, last_tick_flag, last_tick_ms
        while not stop.is_set():
            try:
                async with websockets.connect(url, open_timeout=5) as ws:
                    log.info("Telemetry connected")
                    telem_connected = True
                    last_tick_ms = _ms_now()
                    cur = obs.get_current_scene()
                    if cur:
                        director.note_obs_scene(cur)
                        log.info("Synced OBS program scene=%s", cur)
                    sender = asyncio.create_task(command_sender(ws))
                    try:
                        async for raw in ws:
                            if stop.is_set():
                                break
                            try:
                                msg = json.loads(raw)
                            except json.JSONDecodeError:
                                continue
                            if not isinstance(msg, dict):
                                continue
                            mtype = msg.get("type")
                            now = int(msg.get("ts") or _ms_now())
                            if mtype == "telemetry.tick":
                                last_tick_ms = now
                                telem_connected = True
                                flag = str(msg.get("flag") or "none").lower()
                                if flag != last_tick_flag:
                                    last_tick_flag = flag
                                    apply_flag(director, obs, flag, now_ms=now)
                            elif mtype == "telemetry.event":
                                kind = str(msg.get("kind") or "")
                                if kind == "flag_change":
                                    payload = msg.get("payload") or {}
                                    flag = str(payload.get("flag") or "")
                                    apply_flag(director, obs, flag, now_ms=now)
                                await replay.on_event(msg, now_ms=now)
                            elif mtype == "telemetry.session_reset":
                                await replay.reset_local()
                                last_tick_flag = None
                                log.info(
                                    "Telemetry session reset applied reason=%s",
                                    msg.get("reason"),
                                )
                    finally:
                        sender.cancel()
                        try:
                            await sender
                        except asyncio.CancelledError:
                            pass
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                telem_connected = False
                log.warning("Telemetry disconnected (%s); retry in 2s", type(exc).__name__)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass

    await asyncio.gather(session_poll(), ws_loop())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OBS Session Director (flags + Live/Lobby)")
    p.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to config.local.json",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Log scene switches without calling OBS",
    )
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    t0 = time.perf_counter()
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    log.info("Session director starting")

    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        if EXAMPLE_CONFIG.is_file() and not args.config.exists():
            log.warning("No config.local.json — using example with dryRun forced")
            cfg = load_config(EXAMPLE_CONFIG)
            cfg["dryRun"] = True
        else:
            log.error("Config missing: %s", args.config)
            return 2

    if cfg.get("enabled") is False:
        log.info("enabled=false; exiting")
        return 0

    director = build_session_director(cfg)
    obs = connect_obs(cfg, force_dry=bool(args.dry_run))
    stop = asyncio.Event()

    try:
        asyncio.run(run_director_loop(cfg, director, obs, stop))
    except KeyboardInterrupt:
        log.info("Interrupted")
    finally:
        obs.close()
        elapsed = time.perf_counter() - t0
        log.info("Session director stopped after %.1fs", elapsed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
