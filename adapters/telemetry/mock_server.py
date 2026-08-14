#!/usr/bin/env python3
"""
PiGreco Racing — mock telemetry producer (P3-01).

Emits sample telemetry.tick messages on localhost WebSocket and/or writes
telemetry.json for file-poll consumers. No sim SDK.

See CONTRACT.md and docs/adr/005-telemetry-adapter-port.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from domain_enrich import apply_pos_change, delta_best_ms  # noqa: E402
from domain_events import EventDetector  # noqa: E402
from domain_standings import build_relatives, mock_standings  # noqa: E402

SCHEMA_VERSION = 1
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_HZ = 10.0
SERVER_NAME = "pigreco-telemetry-mock"

DEFAULT_JSON_PATH = HERE / "telemetry.json"

log = logging.getLogger("pigreco.telemetry.mock")
_prev_pos_by_car: dict = {}
detector = EventDetector(sensitivity="normal")


@dataclass(frozen=True)
class MockConfig:
    host: str
    port: int
    hz: float
    mode: str
    json_path: Path
    duration_s: float | None
    sensitivity: str = "normal"


def _ms_now() -> int:
    return int(time.time() * 1000)


def _envelope(msg_type: str, **fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": msg_type,
        "schemaVersion": SCHEMA_VERSION,
        "ts": _ms_now(),
    }
    out.update(fields)
    return out


def build_tick(elapsed_s: float) -> dict[str, Any]:
    """Deterministic fake race snapshot for overlay smoke tests."""
    global _prev_pos_by_car
    # Soft oscillation so gaps / speed look alive without randomness noise.
    wave = math.sin(elapsed_s * 0.35)
    lap_progress = (elapsed_s % 95.0) / 95.0
    position = 3 if wave > -0.6 else 4
    field = 12
    standings = mock_standings(elapsed_s, focus_pos=position, field=field)
    standings, _prev_pos_by_car = apply_pos_change(standings, _prev_pos_by_car)
    focus = next((r for r in standings if r.get("isFocus")), standings[0])
    focus_i = next(i for i, r in enumerate(standings) if r.get("isFocus"))
    gap_ahead = 0 if focus_i == 0 else int(standings[focus_i].get("intervalMs") or 0)
    gap_behind = (
        0
        if focus_i >= len(standings) - 1
        else int(standings[focus_i + 1].get("intervalMs") or 0)
    )
    last_lap = int(focus.get("lastLapMs") or 91234)
    best_lap = int(focus.get("bestLapMs") or 90801)
    flag = "green"
    if int(elapsed_s) % 47 in (12, 13, 14):
        flag = "yellow"
    elif int(elapsed_s) % 91 == 0:
        flag = "blue"
    elif int(elapsed_s) % 113 == 0:
        flag = "white"
    relatives = build_relatives(standings, focus_car_idx=focus.get("carIdx"), window=2)
    lap = 12 + int(elapsed_s // 95)
    laps_total = 25

    return _envelope(
        "telemetry.tick",
        session="race",
        sessionTimeMs=int(elapsed_s * 1000),
        position=position,
        positionOf=field,
        gapAheadMs=gap_ahead,
        gapBehindMs=gap_behind,
        lastLapMs=last_lap,
        bestLapMs=best_lap,
        # P3-06 enrichment
        deltaBestMs=delta_best_ms(last_lap, best_lap),
        inPit=(int(elapsed_s) % 80) in range(40, 45),
        iRating=1850,
        airTempC=24.0,
        trackTempC=32.0,
        sof=2100,
        currentLapMs=int(lap_progress * last_lap),
        lap=lap,
        lapsTotal=laps_total,
        flag=flag,
        trackName="Monza GP",
        carName="Ferrari 296 GT3",
        speedKph=round(210.0 + abs(wave) * 55.0, 1),
        gear=max(1, min(6, int(2 + abs(wave) * 4))),
        rpm=int(4500 + abs(wave) * 3500),
        fuelPct=round(max(5.0, 62.0 - elapsed_s * 0.04), 1),
        connected=True,
        # P3-02 broadcast fields
        isReplay=True,
        focusCarIdx=focus.get("carIdx"),
        focusDriverName=focus.get("name"),
        focusCarNumber=focus.get("carNumber"),
        focusClassPosition=position,
        sessionLapsRemain=max(0, laps_total - lap),
        sessionTimeRemainMs=None,
        standings=standings,
        relatives=relatives,
    )


def write_tick_file(path: Path, tick: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(tick, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), None)
    if not isinstance(level, int):
        raise SystemExit(f"Invalid --log-level: {level_name}")
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Mock PiGreco telemetry producer (WebSocket and/or JSON file)."
    )
    p.add_argument(
        "--mode",
        choices=("ws", "file", "both"),
        default="ws",
        help="ws=WebSocket (needs websockets), file=stdlib JSON writer, both=mirror",
    )
    p.add_argument("--host", default=DEFAULT_HOST, help="WebSocket bind host")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help="WebSocket port")
    p.add_argument("--hz", type=float, default=DEFAULT_HZ, help="Tick rate")
    p.add_argument(
        "--json-path",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help="Path for telemetry.json when mode is file/both",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional run duration in seconds (default: until Ctrl+C)",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        help="DEBUG | INFO | WARNING | ERROR (default INFO)",
    )
    p.add_argument(
        "--sensitivity",
        choices=("calm", "normal", "hype"),
        default="normal",
        help="Event detector sensitivity (default: normal)",
    )
    return p.parse_args(argv)


def _try_import_websockets():
    try:
        import websockets  # type: ignore
        from websockets.asyncio.server import serve  # type: ignore

        return websockets, serve
    except ImportError:
        return None, None


async def _run_file_loop(cfg: MockConfig, stop: asyncio.Event) -> int:
    interval = 1.0 / max(cfg.hz, 0.1)
    started = time.perf_counter()
    ticks = 0
    log.info(
        "File mode started path=%s hz=%.2f",
        cfg.json_path,
        cfg.hz,
    )
    try:
        while not stop.is_set():
            if cfg.duration_s is not None and (time.perf_counter() - started) >= cfg.duration_s:
                log.info("Duration reached; stopping file loop")
                break
            elapsed = time.perf_counter() - started
            tick = build_tick(elapsed)
            t0 = time.perf_counter()
            # File fallback stores the latest tick only; telemetry.event is WS-only.
            write_tick_file(cfg.json_path, tick)
            write_ms = (time.perf_counter() - t0) * 1000
            ticks += 1
            if ticks == 1 or ticks % max(1, int(cfg.hz * 5)) == 0:
                log.info(
                    "File tick #%d position=%s gapAheadMs=%s write=%.1fms",
                    ticks,
                    tick.get("position"),
                    tick.get("gapAheadMs"),
                    write_ms,
                )
            else:
                log.debug("File tick #%d write=%.1fms", ticks, write_ms)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
    finally:
        total_s = time.perf_counter() - started
        rate = ticks / total_s if total_s > 0 else 0.0
        log.info(
            "File mode ended ticks=%d duration=%.2fs avg_hz=%.2f path=%s",
            ticks,
            total_s,
            rate,
            cfg.json_path,
        )
    return ticks


async def _run_ws_loop(cfg: MockConfig, stop: asyncio.Event, also_file: bool) -> int:
    websockets, serve = _try_import_websockets()
    if serve is None:
        log.error(
            "Package 'websockets' is required for --mode %s. "
            "Install with: pip install websockets  "
            "Or use: python adapters/telemetry/mock_server.py --mode file",
            cfg.mode,
        )
        return -1

    clients: set[Any] = set()
    interval = 1.0 / max(cfg.hz, 0.1)
    started = time.perf_counter()
    ticks = 0

    async def handler(websocket: Any) -> None:
        clients.add(websocket)
        peer = getattr(websocket, "remote_address", None)
        log.info("Client connected peer=%s total=%d", peer, len(clients))
        hello = _envelope(
            "telemetry.hello",
            server=SERVER_NAME,
            tickHz=cfg.hz,
            modes=["websocket"] + (["file"] if also_file else []),
        )
        await websocket.send(json.dumps(hello, separators=(",", ":")))
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning("Ignoring non-JSON client frame")
                    continue
                if msg.get("type") == "client.ping":
                    pong = _envelope(
                        "server.pong",
                        pingTs=msg.get("ts"),
                    )
                    await websocket.send(json.dumps(pong, separators=(",", ":")))
                    log.debug("Pong sent peer=%s", peer)
        except Exception as exc:  # noqa: BLE001 — connection lifecycle
            log.debug("Client handler ended peer=%s err=%s", peer, exc)
        finally:
            clients.discard(websocket)
            log.info("Client disconnected peer=%s total=%d", peer, len(clients))

    log.info(
        "WebSocket mode starting url=ws://%s:%d hz=%.2f also_file=%s",
        cfg.host,
        cfg.port,
        cfg.hz,
        also_file,
    )

    async with serve(handler, cfg.host, cfg.port):
        log.info("WebSocket listening ws://%s:%d", cfg.host, cfg.port)
        status = _envelope(
            "telemetry.status",
            connected=True,
            reason="mock_running",
        )
        # Broadcast loop
        while not stop.is_set():
            if cfg.duration_s is not None and (time.perf_counter() - started) >= cfg.duration_s:
                log.info("Duration reached; stopping WebSocket loop")
                break
            elapsed = time.perf_counter() - started
            tick = build_tick(elapsed)
            events = detector.feed(tick)
            payload = json.dumps(tick, separators=(",", ":"))
            event_payloads = [
                json.dumps(ev, separators=(",", ":")) for ev in events
            ]
            t0 = time.perf_counter()
            if also_file:
                # File fallback stores the latest tick only; events are WS-only.
                write_tick_file(cfg.json_path, tick)
            for ev in events:
                log.info("event kind=%s id=%s", ev["kind"], ev["eventId"])
            dead: list[Any] = []
            for ws in list(clients):
                try:
                    await ws.send(payload)
                    for ep in event_payloads:
                        await ws.send(ep)
                except Exception:  # noqa: BLE001
                    dead.append(ws)
            for ws in dead:
                clients.discard(ws)
            send_ms = (time.perf_counter() - t0) * 1000
            ticks += 1
            if ticks == 1 or ticks % max(1, int(cfg.hz * 5)) == 0:
                log.info(
                    "WS tick #%d clients=%d position=%s gapAheadMs=%s send=%.1fms",
                    ticks,
                    len(clients),
                    tick.get("position"),
                    tick.get("gapAheadMs"),
                    send_ms,
                )
            else:
                log.debug(
                    "WS tick #%d clients=%d send=%.1fms",
                    ticks,
                    len(clients),
                    send_ms,
                )
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

        # Notify remaining clients
        goodbye = json.dumps(
            _envelope("telemetry.status", connected=False, reason="mock_stopped"),
            separators=(",", ":"),
        )
        for ws in list(clients):
            try:
                await ws.send(goodbye)
            except Exception:  # noqa: BLE001
                pass

    total_s = time.perf_counter() - started
    rate = ticks / total_s if total_s > 0 else 0.0
    log.info(
        "WebSocket mode ended ticks=%d duration=%.2fs avg_hz=%.2f last_status=%s",
        ticks,
        total_s,
        rate,
        status.get("reason"),
    )
    return ticks


async def async_main(cfg: MockConfig) -> int:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        if not stop.is_set():
            log.info("Stop requested")
            stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Windows: signal handlers in asyncio are limited
            signal.signal(sig, lambda *_: _request_stop())

    wall0 = time.perf_counter()
    log.info(
        "Mock telemetry start mode=%s schemaVersion=%d sensitivity=%s",
        cfg.mode,
        SCHEMA_VERSION,
        cfg.sensitivity,
    )

    ticks = 0
    if cfg.mode == "file":
        ticks = await _run_file_loop(cfg, stop)
    elif cfg.mode == "ws":
        ticks = await _run_ws_loop(cfg, stop, also_file=False)
    else:
        ticks = await _run_ws_loop(cfg, stop, also_file=True)

    if ticks < 0:
        log.error("Mock telemetry failed total=%.2fs", time.perf_counter() - wall0)
        return 1

    log.info(
        "Mock telemetry success ticks=%d total=%.2fs",
        ticks,
        time.perf_counter() - wall0,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    if args.hz <= 0:
        log.error("hz must be > 0")
        return 2
    detector.set_sensitivity(args.sensitivity)
    cfg = MockConfig(
        host=args.host,
        port=args.port,
        hz=args.hz,
        mode=args.mode,
        json_path=args.json_path.resolve(),
        duration_s=args.duration,
        sensitivity=args.sensitivity,
    )
    try:
        return asyncio.run(async_main(cfg))
    except KeyboardInterrupt:
        log.info("Interrupted")
        return 0


if __name__ == "__main__":
    sys.exit(main())
