#!/usr/bin/env python3
"""
PiGreco / S.Marcato — iRacing telemetry bridge (P3-02).

Reads the local iRacing SDK (live or replay), builds CONTRACT telemetry.tick
messages (with standings/relatives), and serves them on ws://127.0.0.1:8765.

Replay-aware: when CarIdxPosition is unreliable, standings come from
lap + LapDistPct.

Requires: pip install websockets pyirsdk
iRacing must be running (replay or session).

See CONTRACT.md and docs/TELEMETRY_BROADCAST.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from domain_enrich import apply_pos_change, delta_best_ms  # noqa: E402
from domain_events import EventDetector  # noqa: E402
from domain_standings import build_relatives, standings_from_cars  # noqa: E402

SCHEMA_VERSION = 1
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_HZ = 10.0
SERVER_NAME = "pigreco-telemetry-iracing"
DEFAULT_JSON_PATH = HERE / "telemetry.json"

log = logging.getLogger("pigreco.telemetry.iracing")
_prev_pos_by_car: dict = {}
_last_focus_car_idx: Any = None
_last_session_time_ms: int | None = None
detector = EventDetector(sensitivity="normal")
SESSION_BACKJUMP_MS = 1000


def continuity_broke(
    prev_focus: Any,
    prev_session_ms: Any,
    focus: Any,
    session_ms: Any,
    *,
    backjump_ms: int = SESSION_BACKJUMP_MS,
) -> bool:
    """True on camera cut or a meaningful session-time rewind (replay seek)."""
    if prev_focus is not None and focus is not None and focus != prev_focus:
        return True
    if (
        isinstance(prev_session_ms, (int, float))
        and isinstance(session_ms, (int, float))
        and (prev_session_ms - session_ms) >= backjump_ms
    ):
        return True
    return False


def reset_continuity() -> None:
    """Clear event + pos-change memory (disconnect / invalid tick)."""
    global _prev_pos_by_car, _last_focus_car_idx, _last_session_time_ms
    had_state = (
        detector._prev is not None
        or bool(_prev_pos_by_car)
        or _last_focus_car_idx is not None
    )
    detector.reset()
    _prev_pos_by_car = {}
    _last_focus_car_idx = None
    _last_session_time_ms = None
    if had_state:
        log.info("continuity reset detector and pos-change map")


def note_tick_continuity(*, focus_car_idx: Any, session_time_ms: Any) -> bool:
    """Reset detector + pos map on camera cut or session rewind. Returns True if reset."""
    global _prev_pos_by_car, _last_focus_car_idx, _last_session_time_ms
    broke = continuity_broke(
        _last_focus_car_idx,
        _last_session_time_ms,
        focus_car_idx,
        session_time_ms,
    )
    if broke:
        detector.reset()
        _prev_pos_by_car = {}
        log.info(
            "continuity reset focusCarIdx %s→%s sessionTimeMs %s→%s",
            _last_focus_car_idx,
            focus_car_idx,
            _last_session_time_ms,
            session_time_ms,
        )
    _last_focus_car_idx = focus_car_idx
    if isinstance(session_time_ms, (int, float)):
        _last_session_time_ms = int(session_time_ms)
    return broke

# SessionFlags bits (subset)
_FLAG_CHECKERED = 0x00000001
_FLAG_WHITE = 0x00000002
_FLAG_GREEN = 0x00000004
_FLAG_YELLOW = 0x00000008
_FLAG_RED = 0x00000010
_FLAG_BLUE = 0x00000040
_FLAG_BLACK = 0x00000100
_FLAG_MEATBALL = 0x00008000


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


def _flag_name(session_flags: int | None) -> str:
    if not session_flags:
        return "none"
    f = int(session_flags)
    if f & _FLAG_CHECKERED:
        return "checkered"
    if f & _FLAG_RED:
        return "red"
    if f & _FLAG_YELLOW:
        return "yellow"
    if f & _FLAG_WHITE:
        return "white"
    if f & _FLAG_BLUE:
        return "blue"
    if f & _FLAG_BLACK:
        return "black"
    if f & _FLAG_MEATBALL:
        return "meatball"
    if f & _FLAG_GREEN:
        return "green"
    return "none"


# iRacing uses 32767 (INT16 max) for "unlimited / N/A" remaining laps
_LAPS_REMAIN_SENTINEL = 32000


def _sanitize_laps_remain(val: Any) -> int | None:
    if val is None:
        return None
    try:
        n = int(val)
    except (TypeError, ValueError):
        return None
    if n < 0 or n >= _LAPS_REMAIN_SENTINEL:
        return None
    return n


def _session_kind(session_type: str | None) -> str:
    if not session_type:
        return "unknown"
    t = session_type.lower()
    if "race" in t:
        return "race"
    if "qual" in t:
        return "quali"
    if "pract" in t or "warm" in t:
        return "practice"
    if "cool" in t:
        return "cooldown"
    return "unknown"


def _safe_get(ir: Any, key: str, default: Any = None) -> Any:
    try:
        val = ir[key]
        return default if val is None else val
    except Exception:  # noqa: BLE001
        return default


def _num_or_none(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _driver_map(ir: Any) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    try:
        drivers = ir["DriverInfo"]["Drivers"]
    except Exception:  # noqa: BLE001
        return out
    for d in drivers or []:
        try:
            idx = int(d.get("CarIdx"))
        except (TypeError, ValueError):
            continue
        if idx < 0:
            continue
        # Skip pace car typically CarIsPaceCar
        if d.get("CarIsPaceCar") or d.get("CarIsAI") and d.get("UserName") == "Pace Car":
            if d.get("CarIsPaceCar"):
                continue
        irating_raw = d.get("IRating")
        if irating_raw is None:
            irating_raw = d.get("iRating")
        irating = None
        if irating_raw is not None:
            try:
                irating = int(irating_raw)
            except (TypeError, ValueError):
                irating = None
        out[idx] = {
            "carIdx": idx,
            "name": d.get("UserName") or d.get("AbbrevName") or "",
            "carNumber": str(d.get("CarNumber") or d.get("CarNumberRaw") or ""),
            "class": d.get("CarClassShortName") or d.get("CarClassStr") or None,
            "carName": d.get("CarScreenName") or d.get("CarPath") or None,
            "iRating": irating,
        }
    return out


def build_tick_from_ir(ir: Any) -> dict[str, Any] | None:
    """Return a telemetry.tick dict, or None if not connected / no data."""
    global _prev_pos_by_car
    if not getattr(ir, "is_initialized", False) or not getattr(ir, "is_connected", False):
        return None

    ir.freeze_var_buffer_latest()
    try:
        is_replay = bool(_safe_get(ir, "IsReplayPlaying", False))
        cam_idx = _safe_get(ir, "CamCarIdx", None)
        if cam_idx is None:
            cam_idx = _safe_get(ir, "PlayerCarIdx", 0)
        try:
            focus_idx = int(cam_idx)
        except (TypeError, ValueError):
            focus_idx = 0

        laps = _safe_get(ir, "CarIdxLap", []) or []
        dists = _safe_get(ir, "CarIdxLapDistPct", []) or []
        surfaces = _safe_get(ir, "CarIdxTrackSurface", []) or []
        positions = _safe_get(ir, "CarIdxPosition", []) or []
        class_pos = _safe_get(ir, "CarIdxClassPosition", []) or []
        last_laps = _safe_get(ir, "CarIdxLastLapTime", []) or []
        best_laps = _safe_get(ir, "CarIdxBestLapTime", []) or []
        pit_flags = _safe_get(ir, "CarIdxOnPitRoad", []) or []

        drivers = _driver_map(ir)
        n = max(len(laps), len(dists), len(positions))
        pit_by_idx: dict[int, bool] = {}
        for i, flag in enumerate(pit_flags):
            try:
                pit_by_idx[i] = bool(flag)
            except (TypeError, ValueError):
                continue
        if focus_idx not in pit_by_idx:
            on_pit = _safe_get(ir, "OnPitRoad", None)
            if on_pit is not None:
                pit_by_idx[focus_idx] = bool(on_pit)
        cars: list[dict[str, Any]] = []
        official_valid = 0
        for i in range(n):
            if i not in drivers:
                continue
            lap = laps[i] if i < len(laps) else -1
            dist = dists[i] if i < len(dists) else -1.0
            try:
                lap_i = int(lap)
            except (TypeError, ValueError):
                lap_i = -1
            try:
                dist_f = float(dist)
            except (TypeError, ValueError):
                dist_f = -1.0
            if lap_i < 0 or dist_f < 0:
                continue
            # NotInWorld = -1 typically
            if i < len(surfaces):
                try:
                    if int(surfaces[i]) < 0:
                        continue
                except (TypeError, ValueError):
                    pass
            off = positions[i] if i < len(positions) else -1
            try:
                off_i = int(off)
            except (TypeError, ValueError):
                off_i = -1
            if off_i > 0:
                official_valid += 1
            last_ms = None
            best_ms = None
            if i < len(last_laps):
                try:
                    lt = float(last_laps[i])
                    if lt > 0:
                        last_ms = int(lt * 1000)
                except (TypeError, ValueError):
                    pass
            if i < len(best_laps):
                try:
                    bt = float(best_laps[i])
                    if bt > 0:
                        best_ms = int(bt * 1000)
                except (TypeError, ValueError):
                    pass
            info = drivers[i]
            cars.append(
                {
                    **info,
                    "lap": lap_i,
                    "distPct": dist_f,
                    "officialPos": off_i,
                    "lastLapMs": last_ms,
                    "bestLapMs": best_ms,
                }
            )

        session_time = _safe_get(ir, "SessionTime", None)
        session_time_ms = None
        if session_time is not None:
            try:
                session_time_ms = int(float(session_time) * 1000)
            except (TypeError, ValueError):
                pass
        note_tick_continuity(focus_car_idx=focus_idx, session_time_ms=session_time_ms)

        # Prefer official positions only when enough cars have them and not in replay
        use_official = (not is_replay) and official_valid >= max(2, len(cars) // 2)
        est_lap = 90000.0
        # Estimate lap time from focus best/last if available
        for c in cars:
            if c.get("carIdx") == focus_idx and c.get("bestLapMs"):
                est_lap = float(c["bestLapMs"])
                break

        standings = standings_from_cars(
            cars,
            focus_car_idx=focus_idx,
            use_official_pos=use_official,
            est_lap_ms=est_lap,
        )
        standings, _prev_pos_by_car = apply_pos_change(standings, _prev_pos_by_car)
        for r in standings:
            idx = r.get("carIdx")
            if idx in pit_by_idx:
                r["inPit"] = pit_by_idx[idx]
            info = drivers.get(idx) if idx is not None else None
            if info is not None and "iRating" in info:
                r["iRating"] = info.get("iRating")
        relatives = build_relatives(standings, focus_car_idx=focus_idx, window=2)

        focus_row = next((r for r in standings if r.get("carIdx") == focus_idx), None)
        if focus_row is None and standings:
            focus_row = standings[0]

        focus_i = 0
        if focus_row:
            for i, r in enumerate(standings):
                if r.get("carIdx") == focus_row.get("carIdx"):
                    focus_i = i
                    break

        gap_ahead = 0 if focus_i == 0 else int(standings[focus_i].get("intervalMs") or 0)
        gap_behind = (
            0
            if focus_i >= len(standings) - 1
            else int(standings[focus_i + 1].get("intervalMs") or 0)
        )

        session_remain = _safe_get(ir, "SessionTimeRemain", None)
        laps_remain = _safe_get(ir, "SessionLapsRemainEx", None)
        if laps_remain is None:
            laps_remain = _safe_get(ir, "SessionLapsRemain", None)
        race_laps = _safe_get(ir, "RaceLaps", None)
        session_flags = _safe_get(ir, "SessionFlags", 0)
        speed = _safe_get(ir, "Speed", None)
        gear = _safe_get(ir, "Gear", None)
        rpm = _safe_get(ir, "RPM", None)
        fuel_pct = _safe_get(ir, "FuelLevelPct", None)

        track_name = None
        session_type = None
        try:
            weekend = ir["WeekendInfo"]
            track_name = weekend.get("TrackDisplayName") or weekend.get("TrackName")
        except Exception:  # noqa: BLE001
            pass
        try:
            # Current session type from SessionInfo
            sessions = ir["SessionInfo"]["Sessions"]
            sid = int(_safe_get(ir, "SessionNum", 0) or 0)
            if sessions and 0 <= sid < len(sessions):
                session_type = sessions[sid].get("SessionType")
        except Exception:  # noqa: BLE001
            pass

        focus_info = drivers.get(focus_idx, {})
        class_p = None
        if focus_idx < len(class_pos):
            try:
                cp = int(class_pos[focus_idx])
                if cp > 0:
                    class_p = cp
            except (TypeError, ValueError):
                pass

        speed_kph = None
        if speed is not None:
            try:
                speed_kph = round(float(speed) * 3.6, 1)
            except (TypeError, ValueError):
                pass

        fuel = None
        if fuel_pct is not None:
            try:
                fuel = round(float(fuel_pct) * 100.0, 1)
            except (TypeError, ValueError):
                pass

        session_remain_ms = None
        if session_remain is not None:
            try:
                sr = float(session_remain)
                if sr >= 0 and sr < 600000:
                    session_remain_ms = int(sr * 1000)
            except (TypeError, ValueError):
                pass

        lap_focus = None
        if focus_idx < len(laps):
            try:
                lap_focus = int(laps[focus_idx])
                if lap_focus < 0:
                    lap_focus = None
            except (TypeError, ValueError):
                pass

        session_kind = _session_kind(session_type)
        flag = _flag_name(session_flags)
        # Replay / quiet SDK often reports 0 flags — treat active sessions as green
        if flag == "none" and session_kind in ("race", "practice", "quali", "cooldown"):
            flag = "green"

        last_ms = focus_row.get("lastLapMs") if focus_row else None
        best_ms = focus_row.get("bestLapMs") if focus_row else None
        track_temp = _safe_get(ir, "TrackTemp", None)
        if track_temp is None:
            track_temp = _safe_get(ir, "TrackTempCrew", None)

        return _envelope(
            "telemetry.tick",
            session=session_kind,
            sessionTimeMs=session_time_ms,
            position=focus_row.get("pos") if focus_row else None,
            positionOf=len(standings) or None,
            gapAheadMs=gap_ahead,
            gapBehindMs=gap_behind,
            lastLapMs=last_ms,
            bestLapMs=best_ms,
            deltaBestMs=delta_best_ms(last_ms, best_ms),
            inPit=pit_by_idx.get(focus_idx),
            iRating=focus_info.get("iRating"),
            airTempC=_num_or_none(_safe_get(ir, "AirTemp", None)),
            trackTempC=_num_or_none(track_temp),
            sof=None,
            currentLapMs=None,
            lap=lap_focus if lap_focus is not None else race_laps,
            lapsTotal=None,
            flag=flag,
            trackName=track_name,
            carName=focus_info.get("carName"),
            speedKph=speed_kph,
            gear=gear,
            rpm=int(rpm) if isinstance(rpm, (int, float)) else None,
            fuelPct=fuel,
            connected=True,
            isReplay=is_replay,
            focusCarIdx=focus_idx,
            focusDriverName=focus_info.get("name") or (focus_row.get("name") if focus_row else None),
            focusCarNumber=focus_info.get("carNumber")
            or (focus_row.get("carNumber") if focus_row else None),
            focusClassPosition=class_p or (focus_row.get("pos") if focus_row else None),
            sessionLapsRemain=_sanitize_laps_remain(laps_remain),
            sessionTimeRemainMs=session_remain_ms,
            standings=standings,
            relatives=relatives,
        )
    finally:
        try:
            ir.unfreeze_var_buffer_latest()
        except Exception:  # noqa: BLE001
            pass


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
    p = argparse.ArgumentParser(description="iRacing → PiGreco telemetry WebSocket bridge")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--hz", type=float, default=DEFAULT_HZ)
    p.add_argument("--also-file", action="store_true", help="Also write telemetry.json")
    p.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    p.add_argument(
        "--ibt",
        action="store_true",
        help=(
            "Ask iRacing to record native .ibt disk telemetry "
            "(Documents/iRacing/telemetry). Optional; off by default."
        ),
    )
    p.add_argument(
        "--ibt-dir",
        type=Path,
        default=None,
        help="Override folder to log for IBT output (sim still writes to its default)",
    )
    p.add_argument("--log-level", default="INFO")
    p.add_argument(
        "--sensitivity",
        choices=("calm", "normal", "hype"),
        default="normal",
        help="Event detector sensitivity (default: normal)",
    )
    return p.parse_args(argv)


def default_ibt_dir() -> Path:
    docs = Path.home() / "Documents" / "iRacing" / "telemetry"
    return docs


def ibt_start(ir: Any, irsdk_mod: Any, *, ibt_dir: Path) -> bool:
    """Broadcast TelemCommand.start so the sim writes a native .ibt file."""
    try:
        ir.telem_command(irsdk_mod.TelemCommandMode.start)
        log.info(
            "IBT recording START requested — files land under %s "
            "(sim records while in-car; replay/spectator may skip)",
            ibt_dir,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("IBT start failed: %s", exc)
        return False


def ibt_stop(ir: Any, irsdk_mod: Any) -> None:
    try:
        ir.telem_command(irsdk_mod.TelemCommandMode.stop)
        log.info("IBT recording STOP requested")
    except Exception as exc:  # noqa: BLE001
        log.warning("IBT stop failed: %s", exc)


def _try_import_irsdk():
    try:
        import irsdk  # type: ignore

        return irsdk
    except ImportError:
        return None


def _try_import_websockets():
    try:
        from websockets.asyncio.server import serve  # type: ignore

        return serve
    except ImportError:
        return None


async def async_main(args: argparse.Namespace) -> int:
    irsdk = _try_import_irsdk()
    if irsdk is None:
        log.error("Package 'pyirsdk' required. Install: pip install pyirsdk")
        return 2
    serve = _try_import_websockets()
    if serve is None:
        log.error("Package 'websockets' required. Install: pip install websockets")
        return 2

    ir = irsdk.IRSDK()
    if not ir.startup():
        log.warning("iRacing SDK startup returned False — waiting for sim…")

    clients: set[Any] = set()
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
            signal.signal(sig, lambda *_: _request_stop())

    async def handler(websocket: Any) -> None:
        clients.add(websocket)
        peer = getattr(websocket, "remote_address", None)
        log.info("Client connected peer=%s total=%d", peer, len(clients))
        hello = _envelope(
            "telemetry.hello",
            server=SERVER_NAME,
            tickHz=args.hz,
            modes=["websocket"] + (["file"] if args.also_file else []),
        )
        await websocket.send(json.dumps(hello, separators=(",", ":")))
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "client.ping":
                    await websocket.send(
                        json.dumps(
                            _envelope("server.pong", pingTs=msg.get("ts")),
                            separators=(",", ":"),
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            log.debug("Client ended peer=%s err=%s", peer, exc)
        finally:
            clients.discard(websocket)
            log.info("Client disconnected peer=%s total=%d", peer, len(clients))

    interval = 1.0 / max(args.hz, 0.1)
    started = time.perf_counter()
    ticks = 0
    connected_logged = False
    ibt_armed = False
    ibt_dir = (args.ibt_dir or default_ibt_dir()).expanduser().resolve()

    log.info(
        "iRacing bridge starting ws://%s:%d hz=%.1f ibt=%s sensitivity=%s",
        args.host,
        args.port,
        args.hz,
        bool(args.ibt),
        args.sensitivity,
    )
    if args.ibt:
        log.info("IBT folder (sim-managed): %s", ibt_dir)

    async with serve(handler, args.host, args.port):
        while not stop.is_set():
            t0 = time.perf_counter()
            if not ir.is_initialized or not ir.is_connected:
                if not ir.startup():
                    if connected_logged:
                        log.warning("iRacing disconnected")
                        reset_continuity()
                        if ibt_armed:
                            ibt_stop(ir, irsdk)
                            ibt_armed = False
                        connected_logged = False
                        status = _envelope(
                            "telemetry.status",
                            connected=False,
                            reason="sim_disconnected",
                        )
                        payload = json.dumps(status, separators=(",", ":"))
                        for ws in list(clients):
                            try:
                                await ws.send(payload)
                            except Exception:  # noqa: BLE001
                                pass
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=interval)
                    except asyncio.TimeoutError:
                        pass
                    continue

            if not connected_logged:
                is_replay = bool(_safe_get(ir, "IsReplayPlaying", False))
                log.info("iRacing connected (replay=%s)", is_replay)
                connected_logged = True
                if args.ibt and not ibt_armed:
                    if is_replay:
                        log.warning(
                            "IBT: replay session — disk telem often empty; "
                            "prefer live in-car for Motec/IBT files"
                        )
                    ibt_armed = ibt_start(ir, irsdk, ibt_dir=ibt_dir)

            tick = build_tick_from_ir(ir)
            if tick is None:
                reset_continuity()
                try:
                    await asyncio.wait_for(stop.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
                continue

            events = detector.feed(tick)
            payload = json.dumps(tick, separators=(",", ":"))
            event_payloads = [
                json.dumps(ev, separators=(",", ":")) for ev in events
            ]
            if args.also_file:
                # File fallback stores the latest tick only; events are WS-only.
                write_tick_file(args.json_path.resolve(), tick)
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

            ticks += 1
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if ticks == 1 or ticks % max(1, int(args.hz * 5)) == 0:
                log.info(
                    "tick #%d clients=%d pos=%s field=%s replay=%s "
                    "delta=%s pit=%s ir=%s build=%.1fms",
                    ticks,
                    len(clients),
                    tick.get("position"),
                    tick.get("positionOf"),
                    tick.get("isReplay"),
                    tick.get("deltaBestMs"),
                    tick.get("inPit"),
                    tick.get("iRating"),
                    elapsed_ms,
                )

            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    if ibt_armed:
        ibt_stop(ir, irsdk)
        ibt_armed = False

    total_s = time.perf_counter() - started
    log.info(
        "iRacing bridge ended ticks=%d duration=%.2fs avg_hz=%.2f",
        ticks,
        total_s,
        ticks / total_s if total_s > 0 else 0.0,
    )
    try:
        ir.shutdown()
    except Exception:  # noqa: BLE001
        pass
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    if args.hz <= 0:
        log.error("hz must be > 0")
        return 2
    detector.set_sensitivity(args.sensitivity)
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        log.info("Interrupted")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
