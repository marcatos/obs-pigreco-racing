#!/usr/bin/env python3
"""
Session Director (P3-04 + Live↔Lobby).

Listens to PiGreco telemetry WebSocket, watches iRacing processes, optionally
starts the telemetry bridge, and switches OBS scenes:
  - yellow / red / checkered → Flag *
  - green / none → stacked home (Live or Lobby)
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
    FlagDirector,
    FlagDirectorConfig,
    SessionDirector,
    SessionDirectorConfig,
)

log = logging.getLogger("pigreco.session_director")

DEFAULT_CONFIG = HERE / "config.local.json"
EXAMPLE_CONFIG = HERE / "config.example.json"


def _ms_now() -> int:
    return int(time.time() * 1000)


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Copy {EXAMPLE_CONFIG.name} to config.local.json"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return data


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
        )
    )


def build_session_director(cfg: dict[str, Any]) -> SessionDirector:
    scenes = cfg.get("scenes") or {}
    if not isinstance(scenes, dict):
        scenes = {}
    manual = cfg.get("manualScenes")
    manual_set = (
        frozenset(str(x) for x in manual)
        if isinstance(manual, list)
        else frozenset({"Starting Soon", "BRB", "Ending"})
    )
    return SessionDirector(
        SessionDirectorConfig(
            scenes={str(k).lower(): str(v) for k, v in scenes.items()},
            live_scene=str(cfg.get("liveScene") or "Live"),
            lobby_scene=str(cfg.get("lobbyScene") or "Lobby"),
            home_scene=str(cfg.get("homeScene") or cfg.get("liveScene") or "Live"),
            flag_debounce_ms=int(cfg.get("debounceMs") or 1500),
            session_debounce_ms=int(cfg.get("sessionDebounceMs") or 4000),
            manual_scenes=manual_set,
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

    def close(self) -> None:
        return None


class DryRunObs(ObsScenePort):
    def __init__(self) -> None:
        self.last: str | None = None

    def set_scene(self, name: str) -> None:
        self.last = name
        log.info("DRY-RUN set_scene name=%s", name)

    def get_current_scene(self) -> str | None:
        return self.last


class LiveObs(ObsScenePort):
    def __init__(self, host: str, port: int, password: str) -> None:
        from obsws_python import ReqClient  # type: ignore

        self._client = ReqClient(host=host, port=port, password=password, timeout=5)

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

    def close(self) -> None:
        return None


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
        )
        if proc.returncode != 0:
            return False
        lower = proc.stdout.lower()
        return any(n.lower() in lower for n in names)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.debug("process_running failed: %s", exc)
        return False


def telemetry_port_open(host: str = "127.0.0.1", port: int = 8765) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
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
        try:
            if bat.is_file():
                log.info("Starting telemetry via %s %s", bat.name, self.mode)
                self._child = subprocess.Popen(
                    ["cmd", "/c", str(bat), self.mode],
                    cwd=str(ROOT),
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
            elif py.is_file():
                log.info("Starting telemetry via start_telemetry.py %s", self.mode)
                self._child = subprocess.Popen(
                    [sys.executable, str(py), self.mode],
                    cwd=str(ROOT),
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

    log.info("Session director loop url=%s processes=%s", url, proc_names)

    async def session_poll() -> None:
        nonlocal telem_connected
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
            if cur:
                director.note_obs_scene(cur)

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
                        elif mtype == "telemetry.event" and msg.get("kind") == "flag_change":
                            payload = msg.get("payload") or {}
                            flag = str(payload.get("flag") or "")
                            apply_flag(director, obs, flag, now_ms=now)
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
