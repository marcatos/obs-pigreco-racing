#!/usr/bin/env python3
"""
P3-04 — OBS flag director.

Listens to PiGreco telemetry WebSocket and switches OBS scenes on
yellow / red / checkered; returns home on green.

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
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from domain_flag_director import FlagDirector, FlagDirectorConfig  # noqa: E402

log = logging.getLogger("pigreco.flag_director")

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


def build_director(cfg: dict[str, Any]) -> FlagDirector:
    scenes = cfg.get("scenes") or {}
    if not isinstance(scenes, dict):
        scenes = {}
    return FlagDirector(
        FlagDirectorConfig(
            scenes={str(k).lower(): str(v) for k, v in scenes.items()},
            home_scene=str(cfg.get("homeScene") or "Rec * Live"),
            debounce_ms=int(cfg.get("debounceMs") or 1500),
        )
    )


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
    director: FlagDirector,
    obs: ObsScenePort,
    flag: str,
    *,
    now_ms: int | None = None,
) -> str | None:
    scene = director.on_flag(flag, now_ms=now_ms if now_ms is not None else _ms_now())
    if scene:
        obs.set_scene(scene)
    return scene


async def run_ws_loop(
    cfg: dict[str, Any],
    director: FlagDirector,
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
    last_tick_flag: str | None = None
    log.info("Connecting telemetry url=%s", url)

    while not stop.is_set():
        try:
            async with websockets.connect(url, open_timeout=5) as ws:
                log.info("Telemetry connected")
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
                    if mtype == "telemetry.event" and msg.get("kind") == "flag_change":
                        payload = msg.get("payload") or {}
                        flag = str(payload.get("flag") or "")
                        apply_flag(director, obs, flag, now_ms=int(msg.get("ts") or _ms_now()))
                    elif mtype == "telemetry.tick":
                        flag = str(msg.get("flag") or "none").lower()
                        if flag != last_tick_flag:
                            last_tick_flag = flag
                            apply_flag(
                                director, obs, flag, now_ms=int(msg.get("ts") or _ms_now())
                            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("Telemetry disconnected (%s); retry in 2s", type(exc).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OBS flag director (P3-04)")
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
    log.info("Flag director starting")

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

    director = build_director(cfg)
    obs = connect_obs(cfg, force_dry=bool(args.dry_run))
    stop = asyncio.Event()

    try:
        asyncio.run(run_ws_loop(cfg, director, obs, stop))
    except KeyboardInterrupt:
        log.info("Interrupted")
    finally:
        obs.close()
        elapsed = time.perf_counter() - t0
        log.info("Flag director stopped after %.1fs", elapsed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
