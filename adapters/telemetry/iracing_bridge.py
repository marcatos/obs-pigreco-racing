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

from domain_battle import battle_panel_eligible  # noqa: E402
from domain_country import resolve_country  # noqa: E402
from domain_enrich import delta_best_ms  # noqa: E402
from domain_events import EventDetector  # noqa: E402
from domain_grid import (  # noqa: E402
    apply_start_positions,
    parse_qualify_grid,
    race_live_order_ready,
    standings_from_grid_order,
)
from domain_sectors import (  # noqa: E402
    SectorLapTracker,
    current_sector,
    delta_live_ms,
    normalize_sector_starts,
    sectors_payload,
)
from domain_session_reset import (  # noqa: E402
    SessionResetTracker,
    build_session_key,
    session_reset_envelope,
)
from domain_standings import build_relatives, standings_from_cars  # noqa: E402
from domain_track_map import build_map_cars, format_track_id  # noqa: E402

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
_sector_tracker = SectorLapTracker()
_session_tracker = SessionResetTracker()
_session_key_missing_logged = False
_start_by_car: dict[int, int] = {}
_grid_session_key: Any = None
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
    global _start_by_car, _grid_session_key
    had_state = (
        detector._prev is not None
        or bool(_prev_pos_by_car)
        or _last_focus_car_idx is not None
    )
    detector.reset()
    _prev_pos_by_car = {}
    _last_focus_car_idx = None
    _last_session_time_ms = None
    _sector_tracker.reset()
    _start_by_car = {}
    _grid_session_key = None
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
        # Keep sector best/last memory; only drop in-progress open splits.
        _sector_tracker._open = []
        _sector_tracker._prev_dist = None
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
_FLAG_BLUE = 0x00000020
_FLAG_DEBRIS = 0x00000040
_FLAG_BLACK = 0x00010000
_FLAG_MEATBALL = 0x00100000


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
    if f & _FLAG_DEBRIS:
        return "debris"
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


def _session_kind_from_ir(ir: Any, session_num: Any) -> str:
    session_type = None
    try:
        sessions = ir["SessionInfo"]["Sessions"]
        sid = int(session_num or 0)
        if sessions and 0 <= sid < len(sessions):
            session_type = sessions[sid].get("SessionType")
    except Exception:  # noqa: BLE001
        pass
    return _session_kind(session_type)


def note_session_identity(ir: Any, *, now_ms: int) -> dict[str, Any] | None:
    """Latch the current sim identity and return a reset envelope on change."""
    global _session_key_missing_logged
    unique_id = _safe_get(ir, "SessionUniqueID", None)
    session_num = _safe_get(ir, "SessionNum", None)
    track_id = None
    try:
        track_id = ir["WeekendInfo"].get("TrackID")
    except Exception:  # noqa: BLE001
        pass
    key = build_session_key(
        unique_id=unique_id,
        track_id=track_id,
        session_num=session_num,
        session_kind=_session_kind_from_ir(ir, session_num),
    )
    if key is None:
        if not _session_key_missing_logged:
            log.warning(
                "session identity unavailable uniqueId=%r trackId=%r sessionNum=%r",
                unique_id,
                track_id,
                session_num,
            )
            _session_key_missing_logged = True
        return None
    _session_key_missing_logged = False
    event = _session_tracker.note(key, now_ms=now_ms)
    if event is None:
        return None
    reset_continuity()
    log.info(
        "session reset reason=%s previous=%s current=%s",
        event["reason"],
        event["previousKey"],
        event["sessionKey"],
    )
    return session_reset_envelope(
        reason=event["reason"],
        session_key=event["sessionKey"],
        previous_key=event["previousKey"],
        ts=now_ms,
    )


def handle_telemetry_command(
    msg: dict[str, Any],
    *,
    now_ms: int | None = None,
) -> dict[str, Any] | None:
    """Apply supported client commands and return the frame to broadcast."""
    if msg.get("type") != "telemetry.command":
        return None
    command = msg.get("command")
    if command != "session_reset":
        log.warning("unsupported telemetry command command=%r", command)
        return None
    if now_ms is None:
        try:
            now_ms = int(msg.get("ts") or _ms_now())
        except (TypeError, ValueError):
            now_ms = _ms_now()
            log.warning("session_reset command has invalid ts=%r", msg.get("ts"))
    reason = str(msg.get("reason") or "manual")
    event = _session_tracker.force(reason=reason, now_ms=now_ms)
    reset_continuity()
    log.info(
        "session reset command reason=%s session=%s",
        event["reason"],
        event["sessionKey"],
    )
    return session_reset_envelope(
        reason=event["reason"],
        session_key=event["sessionKey"],
        previous_key=event["previousKey"],
        ts=now_ms,
    )


def disconnect_session_reset(*, now_ms: int) -> dict[str, Any]:
    """Clear the latched identity and return the disconnect reset frame."""
    previous_key = _session_tracker.current_key
    reset_continuity()
    _session_tracker.clear_key()
    return session_reset_envelope(
        reason="sim_disconnected",
        session_key=None,
        previous_key=previous_key,
        ts=now_ms,
    )


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
            "userId": None,
            "name": d.get("UserName") or d.get("AbbrevName") or "",
            "carNumber": str(d.get("CarNumber") or d.get("CarNumberRaw") or ""),
            "class": d.get("CarClassShortName") or d.get("CarClassStr") or None,
            "carName": d.get("CarScreenName") or d.get("CarPath") or None,
            "iRating": irating,
            "clubName": (str(d.get("ClubName") or "").strip() or None),
        }
        try:
            if d.get("UserID") is not None:
                out[idx]["userId"] = int(d.get("UserID"))
        except (TypeError, ValueError):
            out[idx]["userId"] = None
        country = resolve_country(
            user_id=out[idx].get("userId"),
            name=out[idx].get("name"),
            club_name=out[idx].get("clubName"),
        )
        out[idx]["countryCode"] = country.get("countryCode")
        out[idx]["country"] = country.get("country")
    return out


def build_tick_from_ir(ir: Any) -> dict[str, Any] | None:
    """Return a telemetry.tick dict, or None if not connected / no data."""
    global _prev_pos_by_car, _start_by_car, _grid_session_key
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

        session_type = None
        session_num = _safe_get(ir, "SessionNum", 0)
        try:
            sessions = ir["SessionInfo"]["Sessions"]
            sid = int(session_num or 0)
            if sessions and 0 <= sid < len(sessions):
                session_type = sessions[sid].get("SessionType")
        except Exception:  # noqa: BLE001
            pass
        session_kind = _session_kind(session_type)
        session_state = _safe_get(ir, "SessionState", None)
        pace_mode = _safe_get(ir, "PaceMode", None)
        try:
            session_state_i = int(session_state) if session_state is not None else None
        except (TypeError, ValueError):
            session_state_i = None
        try:
            pace_mode_i = int(pace_mode) if pace_mode is not None else None
        except (TypeError, ValueError):
            pace_mode_i = None

        try:
            sn = int(session_num) if session_num is not None else None
        except (TypeError, ValueError):
            sn = None
        grid_key = (sn, session_kind)
        if grid_key != _grid_session_key:
            _grid_session_key = grid_key
            _start_by_car = {}
            log.info("grid reset sessionNum=%s kind=%s", sn, session_kind)

        if not _start_by_car:
            try:
                qinfo = ir["QualifyResultsInfo"]
                _start_by_car = parse_qualify_grid(qinfo)
                if _start_by_car:
                    log.info(
                        "grid latched QualifyResultsInfo cars=%d",
                        len(_start_by_car),
                    )
            except Exception:  # noqa: BLE001
                pass
        if not _start_by_car and session_kind == "race":
            tmp: dict[int, int] = {}
            for c in cars:
                op = c.get("officialPos")
                try:
                    idx = int(c["carIdx"])
                    opi = int(op)
                except (TypeError, ValueError, KeyError):
                    continue
                if opi > 0:
                    tmp[idx] = opi
            if len(tmp) >= max(2, len(cars) // 2):
                _start_by_car = tmp
                log.info("grid latched CarIdxPosition cars=%d", len(_start_by_car))

        live_order = race_live_order_ready(
            session_kind=session_kind,
            session_state=session_state_i,
            pace_mode=pace_mode_i,
            cars=cars,
        )

        # Prefer official positions only when enough cars have them and not in replay.
        # Race live always uses lap+distPct — CarIdxPosition briefly zeros at S/F and
        # flipping official↔progress reshuffles the whole board + false overtakes.
        use_official = (
            (not is_replay)
            and official_valid >= max(2, len(cars) // 2)
            and not (session_kind == "race" and live_order)
        )
        est_lap = 90000.0
        for c in cars:
            if c.get("carIdx") == focus_idx and c.get("bestLapMs"):
                est_lap = float(c["bestLapMs"])
                break

        if session_kind == "race" and _start_by_car and not live_order:
            # Hold grid through formation / pace / first S/F chaos
            standings = standings_from_grid_order(
                cars,
                focus_car_idx=focus_idx,
                start_by_car=_start_by_car,
            )
        else:
            standings = standings_from_cars(
                cars,
                focus_car_idx=focus_idx,
                use_official_pos=use_official,
                est_lap_ms=est_lap,
            )
            standings = apply_start_positions(
                standings,
                _start_by_car,
                show_delta=bool(_start_by_car),
            )
        new_pos_map: dict[Any, int] = {}
        for r in standings:
            key = r.get("carIdx")
            if key is None:
                key = r.get("carNumber")
            pos = r.get("pos")
            if key is not None and isinstance(pos, (int, float)):
                new_pos_map[key] = int(pos)
        _prev_pos_by_car = new_pos_map
        for r in standings:
            idx = r.get("carIdx")
            if idx in pit_by_idx:
                r["inPit"] = pit_by_idx[idx]
            info = drivers.get(idx) if idx is not None else None
            if info is not None:
                if "iRating" in info:
                    r["iRating"] = info.get("iRating")
                if info.get("userId") is not None:
                    r["userId"] = info.get("userId")
                club = info.get("clubName")
                if club:
                    r["clubName"] = club
                elif "clubName" not in r:
                    r["clubName"] = None
                if info.get("countryCode"):
                    r["countryCode"] = info.get("countryCode")
                    r["country"] = info.get("country")
                else:
                    resolved = resolve_country(
                        user_id=info.get("userId") or r.get("userId"),
                        name=r.get("name") or info.get("name"),
                        club_name=r.get("clubName") or club,
                    )
                    r["countryCode"] = resolved.get("countryCode")
                    r["country"] = resolved.get("country")
            else:
                resolved = resolve_country(name=r.get("name"), club_name=r.get("clubName"))
                r["countryCode"] = resolved.get("countryCode")
                r["country"] = resolved.get("country")
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
        track_id_raw = None
        track_config = None
        try:
            weekend = ir["WeekendInfo"]
            track_name = weekend.get("TrackDisplayName") or weekend.get("TrackName")
            track_id_raw = weekend.get("TrackID")
            track_config = weekend.get("TrackConfigName") or weekend.get("TrackConfig")
        except Exception:  # noqa: BLE001
            pass
        # session_type / session_kind already resolved above for grid gating

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

        yaw = _safe_get(ir, "YawNorth", None)
        if yaw is None:
            yaw = _safe_get(ir, "Yaw", None)

        # —— Sectors (SplitTimeInfo + player lap clock when cam == player) ——
        sector_starts: list[float] = []
        try:
            sti = ir["SplitTimeInfo"]
            if isinstance(sti, dict):
                sector_starts = normalize_sector_starts(sti.get("Sectors"))
            else:
                sector_starts = normalize_sector_starts(sti)
        except Exception:  # noqa: BLE001
            sector_starts = []
        if sector_starts:
            _sector_tracker.set_starts(sector_starts)

        focus_dist = None
        for c in cars:
            if c.get("carIdx") == focus_idx:
                focus_dist = c.get("distPct")
                break

        player_idx = _safe_get(ir, "PlayerCarIdx", None)
        try:
            player_i = int(player_idx) if player_idx is not None else None
        except (TypeError, ValueError):
            player_i = None
        watching_player = player_i is None or player_i == focus_idx

        current_lap_ms = None
        raw_cur = _safe_get(ir, "LapCurrentLapTime", None)
        if raw_cur is not None:
            try:
                cur_s = float(raw_cur)
                if cur_s > 0:
                    current_lap_ms = int(round(cur_s * 1000))
            except (TypeError, ValueError):
                pass

        sector_fields: dict[str, Any] = {
            "sectors": sectors_payload(sector_starts) if sector_starts else None,
            "sector": current_sector(focus_dist, sector_starts) if sector_starts else None,
            "deltaLiveMs": None,
            "lastSectorsMs": None,
            "bestSectorsMs": None,
            "sectorDeltaMs": None,
        }
        if watching_player and sector_starts:
            snap = _sector_tracker.update(
                dist_pct=focus_dist,
                current_lap_ms=current_lap_ms,
                lap=lap_focus if lap_focus is not None else race_laps,
                last_lap_ms=last_ms,
            )
            sector_fields["sector"] = snap.get("sector")
            sector_fields["lastSectorsMs"] = snap.get("lastSectorsMs")
            sector_fields["bestSectorsMs"] = snap.get("bestSectorsMs")
            sector_fields["sectorDeltaMs"] = snap.get("sectorDeltaMs")
            sector_fields["deltaLiveMs"] = delta_live_ms(
                _safe_get(ir, "LapDeltaToBestLap", None),
                _safe_get(ir, "LapDeltaToBestLap_OK", None),
            )
        elif sector_starts:
            sector_fields["sector"] = current_sector(focus_dist, sector_starts)

        live_ready = True
        if session_kind == "race":
            live_ready = bool(live_order)  # same flag already used for grid hold
        battle_eligible = battle_panel_eligible(
            session_kind,
            live_order_ready=live_ready,
            other_cars=max(0, sum(1 for r in standings if r.get("carIdx") is not None) - 1),
        )

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
            currentLapMs=current_lap_ms if watching_player else None,
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
            battleEligible=battle_eligible,
            trackId=format_track_id(track_id_raw, track_name),
            trackConfig=track_config,
            mapCars=build_map_cars(cars, focus_car_idx=focus_idx),
            yawRad=_num_or_none(yaw),
            **sector_fields,
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


async def broadcast_message(clients: set[Any], message: dict[str, Any]) -> None:
    """Broadcast one JSON frame, pruning clients whose send fails."""
    payload = json.dumps(message, separators=(",", ":"))
    dead: list[Any] = []
    for websocket in list(clients):
        try:
            await websocket.send(payload)
        except Exception:  # noqa: BLE001
            dead.append(websocket)
    for websocket in dead:
        clients.discard(websocket)


async def handle_websocket_client(
    websocket: Any,
    clients: set[Any],
    *,
    tick_hz: float,
    also_file: bool,
) -> None:
    """Serve one client and route supported commands through bridge fan-out."""
    clients.add(websocket)
    peer = getattr(websocket, "remote_address", None)
    log.info("Client connected peer=%s total=%d", peer, len(clients))
    hello = _envelope(
        "telemetry.hello",
        server=SERVER_NAME,
        tickHz=tick_hz,
        modes=["websocket"] + (["file"] if also_file else []),
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
            elif msg.get("type") == "telemetry.command":
                event = handle_telemetry_command(msg)
                if event is not None:
                    await broadcast_message(clients, event)
    except Exception as exc:  # noqa: BLE001
        log.debug("Client ended peer=%s err=%s", peer, exc)
    finally:
        clients.discard(websocket)
        log.info("Client disconnected peer=%s total=%d", peer, len(clients))


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
        await handle_websocket_client(
            websocket,
            clients,
            tick_hz=args.hz,
            also_file=args.also_file,
        )

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

    # Bare TCP probes / HTTP GETs on :8765 otherwise spam InvalidMessage tracebacks.
    logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
    logging.getLogger("websockets.asyncio.server").setLevel(logging.CRITICAL)

    async with serve(handler, args.host, args.port):
        while not stop.is_set():
            t0 = time.perf_counter()
            if not ir.is_initialized or not ir.is_connected:
                if not ir.startup():
                    if connected_logged:
                        log.warning("iRacing disconnected")
                        reset_event = disconnect_session_reset(now_ms=_ms_now())
                        if ibt_armed:
                            ibt_stop(ir, irsdk)
                            ibt_armed = False
                        connected_logged = False
                        status = _envelope(
                            "telemetry.status",
                            connected=False,
                            reason="sim_disconnected",
                        )
                        await broadcast_message(clients, reset_event)
                        await broadcast_message(clients, status)
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

            reset_event = note_session_identity(ir, now_ms=_ms_now())
            if reset_event is not None:
                await broadcast_message(clients, reset_event)
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
