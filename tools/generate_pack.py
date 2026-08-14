"""Generate logo PNG and OBS scene collection for PiGreco Racing."""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import logging
import time
import uuid
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageDraw

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("pigreco-obs")

ROOT = Path(__file__).resolve().parents[1]
OVERLAYS = ROOT / "overlays"
ASSETS = OVERLAYS / "assets"
OBS_DIR = ROOT / "obs"
AUDIO_DIR = ROOT / "audio" / "interstitials"

# Match OBS base canvas + stream output (1920x1080) — ADR-002
CANVAS_W = 1920
CANVAS_H = 1080

STREAMCAM_ID = (
    r"Logitech StreamCam:\\?\usb#22vid_046d&pid_0893&mi_00#228&33ee287c&0&0000"
    r"#22{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
)
# Second camera (seat / wide) on this PC — re-pick in OBS if USB port changes
USBCAM_ID = (
    r"USB Camera:\\?\usb#vid_0c6a&pid_646a&mi_00#9&1779791d&0&0000"
    r"#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
)
MIC_ID = "{0.0.1.00000000}.{0679eb69-e8f9-4599-80e1-eef13c5d18e6}"
# OBS window capture id: title:class:exe
IRACING_WINDOW = "iRacing.com Simulator:SimWinClass:iRacingSim64DX11.exe"
PREV_VER = 536936450
CANVAS_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
# Recording-only 2K canvas (ADR-007)
CANVAS_UUID_2K = "c3d4e5f6-a7b8-9012-cdef-1234567890ab"
REC_2K_W = 2560
REC_2K_H = 1440


def new_uuid() -> str:
    return str(uuid.uuid4())


@contextlib.contextmanager
def canvas_context(width: int, height: int, *, canvas_uuid: str | None = None):
    """Temporarily set module canvas constants (stream vs Rec 2K packs)."""
    global CANVAS_W, CANVAS_H, CANVAS_UUID
    prev = (CANVAS_W, CANVAS_H, CANVAS_UUID)
    CANVAS_W, CANVAS_H = int(width), int(height)
    if canvas_uuid:
        CANVAS_UUID = canvas_uuid
    try:
        yield
    finally:
        CANVAS_W, CANVAS_H, CANVAS_UUID = prev


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


# OBS Browser Source + WebSocket: CEF often blocks ws:// from file:// pages.
# Serve telecronaca HTML via the local config server instead.
CONFIG_HTTP_BASE = "http://127.0.0.1:8766"


def overlay_http_url(overlays_dir: Path, html: str, *, query: str = "") -> str:
    """URL under config_server /o/<pack>/… (marcato | overlays)."""
    pack = "marcato" if overlays_dir.name == "overlays-marcato" else "overlays"
    url = f"{CONFIG_HTTP_BASE}/o/{pack}/{html.lstrip('/')}"
    if query:
        url = f"{url}?{query.lstrip('?')}"
    return url


def discover_monitors() -> list[dict]:
    """Return attached monitors sorted left→right with OBS monitor_id when available."""

    class DISPLAY_DEVICE(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("DeviceName", ctypes.c_char * 32),
            ("DeviceString", ctypes.c_char * 128),
            ("StateFlags", wintypes.DWORD),
            ("DeviceID", ctypes.c_char * 128),
            ("DeviceKey", ctypes.c_char * 128),
        ]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", ctypes.c_wchar * 32),
        ]

    user32 = ctypes.windll.user32
    edd_iface = 1
    attached, active = 1, 2
    found: list[dict] = []

    def _enum(hmon, hdc, lprect, lparam):  # noqa: ANN001
        info = MONITORINFOEX()
        info.cbSize = ctypes.sizeof(MONITORINFOEX)
        user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        found.append(
            {
                "device": info.szDevice,
                "x": int(info.rcMonitor.left),
                "y": int(info.rcMonitor.top),
                "w": int(info.rcMonitor.right - info.rcMonitor.left),
                "h": int(info.rcMonitor.bottom - info.rcMonitor.top),
                "primary": bool(info.dwFlags & 1),
                "monitor_id": "",
            }
        )
        return 1

    proto = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_void_p
    )
    user32.EnumDisplayMonitors(0, 0, proto(_enum), 0)

    ids: dict[str, str] = {}
    for adapter in range(16):
        ada = DISPLAY_DEVICE()
        ada.cb = ctypes.sizeof(ada)
        if not user32.EnumDisplayDevicesA(None, adapter, ctypes.byref(ada), 0):
            break
        if not (ada.StateFlags & attached):
            continue
        name = ada.DeviceName.decode(errors="ignore")
        for mon_i in range(8):
            md = DISPLAY_DEVICE()
            md.cb = ctypes.sizeof(md)
            if not user32.EnumDisplayDevicesA(
                ada.DeviceName, mon_i, ctypes.byref(md), edd_iface
            ):
                break
            if md.StateFlags & active:
                ids[name] = md.DeviceID.decode(errors="ignore")

    for m in found:
        m["monitor_id"] = ids.get(m["device"], "")
    found.sort(key=lambda m: (m["x"], m["y"]))
    return found


def monitor_roles(monitors: list[dict] | None = None) -> dict[str, dict | None]:
    """Map left/center/right from physical layout (center = primary, else middle)."""
    mons = monitors if monitors is not None else discover_monitors()
    if not mons:
        return {"left": None, "center": None, "right": None}
    primary = next((m for m in mons if m.get("primary")), mons[len(mons) // 2])
    others = [m for m in mons if m is not primary]
    left = next((m for m in others if m["x"] < primary["x"]), None)
    right = next((m for m in others if m["x"] > primary["x"]), None)
    # If primary is not spatially center, still expose extremes
    if left is None and len(mons) >= 2:
        left = mons[0] if mons[0] is not primary else None
    if right is None and len(mons) >= 2:
        right = mons[-1] if mons[-1] is not primary else None
    return {"left": left, "center": primary, "right": right}


def monitor_capture_settings(mon: dict | None) -> dict:
    """Bind capture by \\\\.\\DISPLAYn (alt_id).

    Identical EDID/DeviceID across triple Odyssey G5 makes OBS's usual
    monitor_id list collide on the primary; the szDevice fallback path is unique.
    Force WGC (method=2): DXGI duplicator also collapses when ids collide.
    """
    settings: dict = {
        "capture_cursor": False,
        "method": 2,  # Windows Graphics Capture
    }
    if mon and mon.get("device"):
        settings["monitor_id"] = mon["device"]
    elif mon and mon.get("monitor_id"):
        settings["monitor_id"] = mon["monitor_id"]
    return settings


def layout_single_monitor(
    name: str,
    source_uuid: str,
    item_id: int,
    mon: dict | None,
    *,
    visible: bool = True,
    locked: bool = False,
) -> dict:
    """Scale one physical monitor to fit the 1920×1080 canvas."""
    w = float(mon["w"]) if mon else 2560.0
    h = float(mon["h"]) if mon else 1440.0
    scale = min(CANVAS_W / w, CANVAS_H / h)
    out_w, out_h = w * scale, h * scale
    x = (CANVAS_W - out_w) / 2.0
    y = (CANVAS_H - out_h) / 2.0
    return scene_item(
        name,
        source_uuid,
        item_id,
        pos=(x, y),
        scale=(scale, scale),
        visible=visible,
        locked=locked,
        scale_ref=(w, h),
    )


def iracing_capture_settings() -> dict:
    return {
        "capture_mode": "window",
        "window": IRACING_WINDOW,
        "capture_cursor": False,
        "capture_audio": True,
        "priority": 2,
    }


# Middle band reserved for game (matches .triple-safe in theme.css).
# Taller than 360 so gameplay isn't a thin strip; Scale Outer crops edges (zoom).
_TRIPLE_SAFE_H = 480.0
# Bottom-band CAM slot (.triple-cam-slot) — must match theme.css + flex inner
_TRIPLE_INNER_W = 1680.0
_TRIPLE_CAM_W = 320.0
_TRIPLE_CAM_H = 180.0
# OBS_BOUNDS_SCALE_INNER / OUTER
_BOUNDS_SCALE_INNER = 2
_BOUNDS_SCALE_OUTER = 3


def triple_band_h() -> float:
    """Height of each letterbox band (top/bottom share leftover canvas)."""
    return (CANVAS_H - _TRIPLE_SAFE_H) / 2.0


def triple_cam_pos(cam_w: float = _TRIPLE_CAM_W, cam_h: float = _TRIPLE_CAM_H) -> tuple[float, float]:
    """Top-left of webcam inside the bottom graphic band CAM frame."""
    inner_left = (CANVAS_W - _TRIPLE_INNER_W) / 2.0
    band_h = triple_band_h()
    band_y = CANVAS_H - band_h
    x = inner_left + _TRIPLE_INNER_W - cam_w
    y = band_y + max(0.0, (band_h - cam_h) / 2.0)
    return x, y


def layout_iracing_window(
    name: str,
    source_uuid: str,
    item_id: int,
    roles: dict[str, dict | None] | None = None,
    *,
    locked: bool = True,
) -> dict:
    """Fit iRacing into the center band, slightly zoomed (crop edges).

    Scale Outer fills the taller strip and crops L/R (or T/B) instead of
    leaving a thin letterboxed ribbon.
    """
    del roles  # size comes from the live source, not assumed desktop span
    band_h = _TRIPLE_SAFE_H
    y = triple_band_h()
    log.info(
        "iRacing window layout: bounds Scale Outer %dx%d at y=%.0f (bands %.0f)",
        CANVAS_W,
        int(band_h),
        y,
        triple_band_h(),
    )
    item = scene_item(
        name,
        source_uuid,
        item_id,
        pos=(0.0, y),
        scale=(1.0, 1.0),
        locked=locked,
        scale_ref=(float(CANVAS_W), float(CANVAS_H)),
        bounds=(float(CANVAS_W), band_h),
        bounds_type=_BOUNDS_SCALE_OUTER,
        bounds_align=0,  # center
    )
    item["bounds_crop"] = True
    return item


def config_autostart_scripts() -> list[dict]:
    """Wire OBS Scripts tool to auto-start the local config panel server.

    Prefer Lua: OBS always embeds Lua. Python OBS scripting often fails with
    system Python 3.12+/3.14 (no matching python3xx.dll for obs-scripting).
    """
    script = (ROOT / "obs" / "scripts" / "pigreco_config_autostart.lua").resolve()
    pack = ROOT.resolve()
    return [
        {
            "path": str(script).replace("\\", "/"),
            "settings": {
                "pack_root": str(pack).replace("\\", "/"),
            },
        }
    ]


def export_logo_png() -> Path:
    """Keep official pi mark as primary logo; only write fallback if missing."""
    t0 = time.perf_counter()
    official = ASSETS / "logo-pi-official.png"
    out = ASSETS / "logo-pigreco.png"
    if official.exists():
        out.write_bytes(official.read_bytes())
        log.info(
            "logo PNG synced from official pi mark -> %s in %.0f ms",
            out,
            (time.perf_counter() - t0) * 1000,
        )
        return out

    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    green = (0, 196, 0, 255)
    d.ellipse((16, 16, size - 16, size - 16), outline=green, width=8)
    d.rectangle((140, 165, 372, 195), fill=green)
    d.rectangle((185, 195, 220, 380), fill=green)
    d.rectangle((292, 195, 327, 380), fill=green)
    img.save(out, "PNG")
    log.info("fallback logo PNG written to %s in %.0f ms", out, (time.perf_counter() - t0) * 1000)
    return out


def source_base(
    name: str,
    source_id: str,
    settings: dict,
    *,
    mixers: int = 0,
    volume: float = 1.0,
    filters: list[dict] | None = None,
) -> dict:
    out = {
        "prev_ver": PREV_VER,
        "name": name,
        "uuid": new_uuid(),
        "id": source_id,
        "versioned_id": source_id,
        "settings": settings,
        "mixers": mixers,
        "sync": 0,
        "flags": 0,
        "volume": volume,
        "balance": 0.5,
        "enabled": True,
        "muted": False,
        "push-to-mute": False,
        "push-to-mute-delay": 0,
        "push-to-talk": False,
        "push-to-talk-delay": 0,
        "hotkeys": {},
        "deinterlace_mode": 0,
        "deinterlace_field_order": 0,
        "monitoring_type": 0,
        "private_settings": {},
    }
    if filters:
        out["filters"] = filters
    return out


# NVIDIA Background Removal (nv-filters.dll) — mode 2 = Quality + Chair
# (keeps seat / mic stand; drops messy room). Requires Video Effects SDK.
NV_GS_MODE_QUALITY_CHAIR = 2


def nv_greenscreen_filter(
    *,
    name: str = "NVIDIA Background Removal",
    mode: int = NV_GS_MODE_QUALITY_CHAIR,
    threshold: float = 0.92,
) -> dict:
    return {
        "prev_ver": PREV_VER,
        "name": name,
        "uuid": new_uuid(),
        "id": "nv_greenscreen_filter",
        "versioned_id": "nv_greenscreen_filter",
        "settings": {
            "mode": int(mode),
            "threshold": float(threshold),
            "processing_interval": 1,
        },
        "enabled": True,
    }


def cam_carbon_backdrop(name: str, *, width: int, height: int, marcato: bool) -> dict:
    """Solid brand plate behind greenscreen cams (OBS color is 0xAABBGGRR)."""
    # #08080A marcato / #080A0C pigreco → ABGR
    color = 0xFF0A0808 if marcato else 0xFF0C0A08
    return source_base(
        name,
        "color_source_v3",
        {"width": int(width), "height": int(height), "color": color},
    )


def dshow_cam(name: str, device_id: str, *, resolution: str = "1920x1080") -> dict:
    return source_base(
        name,
        "dshow_input",
        {
            "video_device_id": device_id,
            "last_video_device_id": device_id,
            "res_type": 1,
            "resolution": resolution,
        },
        filters=[nv_greenscreen_filter()],
    )


def pos_rel(pos: tuple[float, float]) -> dict[str, float]:
    """OBS relative position (pos_from_absolute in obs-scene.c)."""
    x, y = pos
    return {
        "x": (2.0 * x - CANVAS_W) / CANVAS_H,
        "y": (2.0 * y - CANVAS_H) / CANVAS_H,
    }


def scale_rel(scale: tuple[float, float], scale_ref: tuple[float, float]) -> dict[str, float]:
    """OBS relative scale (item_relative_scale — height factor on both axes)."""
    factor = scale_ref[1] / float(CANVAS_H)
    return {
        "x": scale[0] * factor,
        "y": scale[1] * factor,
    }


def size_rel(size: tuple[float, float]) -> dict[str, float]:
    """OBS relative size for bounds (size_from_absolute in obs-scene.c)."""
    return {
        "x": (2.0 * size[0]) / float(CANVAS_H),
        "y": (2.0 * size[1]) / float(CANVAS_H),
    }


def scene_item(
    name: str,
    source_uuid: str,
    item_id: int,
    *,
    pos=(0.0, 0.0),
    scale=(1.0, 1.0),
    visible: bool = True,
    locked: bool = False,
    scale_ref: tuple[float, float] | None = None,
    crop: tuple[int, int, int, int] = (0, 0, 0, 0),
    bounds: tuple[float, float] | None = None,
    bounds_type: int = 0,
    bounds_align: int = 0,
) -> dict:
    ref = scale_ref or (float(CANVAS_W), float(CANVAS_H))
    crop_l, crop_t, crop_r, crop_b = crop
    bx, by = (float(bounds[0]), float(bounds[1])) if bounds else (0.0, 0.0)
    # OBS loads bounds_rel into item->bounds in relative space (not /canvas).
    if bounds and bounds_type:
        brel = size_rel((bx, by))
    else:
        brel = {"x": 0.0, "y": 0.0}
    return {
        "name": name,
        "source_uuid": source_uuid,
        "visible": visible,
        "locked": locked,
        "rot": 0.0,
        "scale_ref": {"x": ref[0], "y": ref[1]},
        "align": 5,  # OBS_ALIGN_LEFT | OBS_ALIGN_TOP
        "bounds_type": int(bounds_type),
        "bounds_align": int(bounds_align),
        "bounds_crop": False,
        "crop_left": int(crop_l),
        "crop_top": int(crop_t),
        "crop_right": int(crop_r),
        "crop_bottom": int(crop_b),
        "id": item_id,
        "group_item_backup": False,
        "pos": {"x": float(pos[0]), "y": float(pos[1])},
        "pos_rel": pos_rel(pos),
        "scale": {"x": float(scale[0]), "y": float(scale[1])},
        "scale_rel": scale_rel(scale, ref),
        "bounds": {"x": bx, "y": by},
        "bounds_rel": brel,
        "scale_filter": "disable",
        "blend_method": "default",
        "blend_type": "normal",
        "show_transition": {"duration": 300},
        "hide_transition": {"duration": 300},
        "private_settings": {},
    }


def transition_source(
    name: str,
    source_id: str,
    settings: dict,
    *,
    volume: float = 1.0,
) -> dict:
    """OBS scene-collection transition entry (same shape as a source)."""
    return {
        "prev_ver": PREV_VER,
        "name": name,
        "uuid": new_uuid(),
        "id": source_id,
        "versioned_id": source_id,
        "settings": settings,
        "mixers": 0,
        "sync": 0,
        "flags": 0,
        "volume": volume,
        "balance": 0.5,
        "enabled": True,
        "muted": False,
        "push-to-mute": False,
        "push-to-mute-delay": 0,
        "push-to-talk": False,
        "push-to-talk-delay": 0,
        "hotkeys": {},
        "deinterlace_mode": 0,
        "deinterlace_field_order": 0,
        "monitoring_type": 0,
        "private_settings": {},
    }


# Move Transition (Exeldro) position flags — see move-transition.h
_POS_EDGE = 1 << 1
_POS_LEFT = 1 << 2
_POS_RIGHT = 1 << 3
_EASE_IN = 1
_EASE_OUT = 2
_EASE_IN_OUT = 3
_EASING_CUBIC = 2
_MOVE_DURATION_MS = 650
_OBS_MOVE_DLL = Path(r"C:\Program Files\obs-studio\obs-plugins\64bit\move-transition.dll")


def move_transition_settings() -> dict:
    """Racing preset: matched morph; appear from left; disappear to right."""
    return {
        "name_part_match": True,
        "name_number_match": True,
        "name_last_word_match": False,
        "easing_match": _EASE_IN_OUT,
        "easing_in": _EASE_IN,
        "easing_out": _EASE_OUT,
        "easing_function_match": _EASING_CUBIC,
        "easing_function_in": _EASING_CUBIC,
        "easing_function_out": _EASING_CUBIC,
        "position_in": _POS_EDGE | _POS_LEFT,
        "position_out": _POS_EDGE | _POS_RIGHT,
        "zoom_in": 0.0,
        "zoom_out": 0.0,
        "curve_match": 0.0,
        "curve_in": -0.5,
        "curve_out": -0.5,
        "transition_in": "fade",
        "transition_out": "fade",
        "transition_match": "",
        "switch_percentage": 50,
        "nested_scenes": True,
        "cache_transitions": False,
    }


def build_transitions(*, overlays_dir: Path, profile: str) -> tuple[list[dict], str, int]:
    """Return (transitions, current_name, duration_ms). Default: Move Transition."""
    if profile == "marcato":
        stinger_path = ROOT / "overlays-marcato" / "stinger" / "marcato-stinger.webm"
        stinger_name = "S.Marcato Stinger"
        move_name = "S.Marcato Move"
    else:
        stinger_path = ROOT / "overlays" / "stinger" / "pigreco-stinger.webm"
        stinger_name = "PiGreco Stinger"
        move_name = "PiGreco Move"

    if not _OBS_MOVE_DLL.is_file():
        log.warning(
            "move-transition.dll missing (%s) — install Move from "
            "https://obsproject.com/forum/resources/move.913/ before using %s",
            _OBS_MOVE_DLL,
            move_name,
        )

    move = transition_source(move_name, "move_transition", move_transition_settings())
    fade = transition_source("Dissolvenza", "fade_transition", {})
    cut = transition_source("Taglio", "cut_transition", {})
    swipe = transition_source(
        "Swipe Racing",
        "swipe_transition",
        {"direction": "right"},
    )
    slide = transition_source(
        "Slide Racing",
        "slide_transition",
        {"direction": "left"},
    )
    flash = transition_source(
        "Flash Carbon",
        "fade_to_color_transition",
        {"color": 0x08080A if profile == "marcato" else 0x080A0C},
    )

    # Move first + default; stinger kept as branded alternative
    transitions = [move, cut, fade, swipe, slide, flash]
    current = move_name
    duration = _MOVE_DURATION_MS
    log.info("move transition default: %s (%d ms)", move_name, duration)

    if stinger_path.is_file():
        # tp_type 0 = milliseconds; ~50% of ~850ms stinger
        stinger = transition_source(
            stinger_name,
            "obs_stinger_transition",
            {
                "path": str(stinger_path.resolve()),
                "transition_point": 420,
                "tp_type": 0,
                "hw_decode": True,
                "audio_monitoring": 0,
                "audio_fade_style": 1,
                "track_matte_enabled": False,
                "preload": True,
            },
            volume=1.0,
        )
        transitions.insert(1, stinger)
        log.info("stinger transition ready (alternate): %s", stinger_path.name)
    else:
        log.warning(
            "stinger WebM missing (%s) — run: python tools/generate_stinger.py --profile %s --with-whoosh",
            stinger_path,
            profile,
        )

    return transitions, current, duration


def make_scene(name: str, items: list[dict]) -> dict:
    hotkeys = {"OBSBasic.SelectScene": []}
    for it in items:
        hotkeys[f"libobs.show_scene_item.{it['id']}"] = []
        hotkeys[f"libobs.hide_scene_item.{it['id']}"] = []
    return {
        "prev_ver": PREV_VER,
        "name": name,
        "uuid": new_uuid(),
        "id": "scene",
        "versioned_id": "scene",
        "settings": {
            "id_counter": max((it["id"] for it in items), default=0),
            "custom_size": False,
            "items": items,
        },
        "mixers": 0,
        "sync": 0,
        "flags": 0,
        "volume": 1.0,
        "balance": 0.5,
        "enabled": True,
        "muted": False,
        "push-to-mute": False,
        "push-to-mute-delay": 0,
        "push-to-talk": False,
        "push-to-talk-delay": 0,
        "hotkeys": hotkeys,
        "deinterlace_mode": 0,
        "deinterlace_field_order": 0,
        "monitoring_type": 0,
        "canvas_uuid": CANVAS_UUID,
        "private_settings": {},
    }


def build_collection(
    *,
    overlays: Path | None = None,
    collection_name: str = "PiGreco Racing",
    output_filename: str = "PiGreco_Racing.json",
    profile: str = "pigreco",
) -> Path:
    t0 = time.perf_counter()
    overlays_dir = overlays or OVERLAYS
    OBS_DIR.mkdir(parents=True, exist_ok=True)

    desktop = source_base(
        "Audio Desktop",
        "wasapi_output_capture",
        {"device_id": "default"},
        mixers=255,
        volume=0.45,
    )
    mic = source_base(
        "Microfono",
        "wasapi_input_capture",
        {"device_id": MIC_ID},
        mixers=255,
        volume=0.85,
    )
    cam = dshow_cam("StreamCam", STREAMCAM_ID)
    cam2 = dshow_cam("Cam 2", USBCAM_ID)
    roles = monitor_roles()
    for role, mon in roles.items():
        if mon:
            log.info(
                "monitor %s: %s %dx%d @%d,%d",
                role,
                mon.get("device"),
                mon["w"],
                mon["h"],
                mon["x"],
                mon["y"],
            )
        else:
            log.warning("monitor %s not detected — pick display in OBS", role)

    mon_left = source_base(
        "Monitor Sinistro",
        "monitor_capture",
        monitor_capture_settings(roles["left"]),
    )
    mon_center = source_base(
        "Monitor Centro",
        "monitor_capture",
        monitor_capture_settings(roles["center"]),
    )
    mon_right = source_base(
        "Monitor Destro",
        "monitor_capture",
        monitor_capture_settings(roles["right"]),
    )
    # Alias for existing Live Singolo scene name
    mon_single = source_base(
        "Monitor Singolo",
        "monitor_capture",
        monitor_capture_settings(roles["center"]),
    )
    game = source_base(
        "Game Capture",
        "game_capture",
        iracing_capture_settings(),
        mixers=255,
    )

    def browser(name: str, html: str, *, query: str = "") -> dict:
        url = file_url(overlays_dir / html)
        if query:
            url = f"{url}?{query.lstrip('?')}"
        return source_base(
            name,
            "browser_source",
            {
                "url": url,
                "width": CANVAS_W,
                "height": CANVAS_H,
                "fps": 30,
                "shutdown": True,
                "restart_when_active": True,
                "webpage_control_level": 1,
            },
        )

    ov_soon = browser("Overlay Starting Soon", "starting-soon.html")
    ov_brb = browser("Overlay BRB", "brb.html")
    ov_end = browser("Overlay Ending", "ending.html")
    ov_live = browser("Overlay Live Chrome", "live-chrome.html")
    ov_triple = None
    ov_triple_live = None
    if profile == "marcato" and (overlays_dir / "triple-frame.html").is_file():
        ov_triple = browser("Overlay Triple Frame", "triple-frame.html", query="badge=LIVE")
        ov_triple_live = browser(
            "Overlay Triple Frame Live", "triple-frame.html", query="cam=1&badge=LIVE"
        )

    def music(name: str, filename: str, *, volume: float = 0.28) -> dict | None:
        path = AUDIO_DIR / filename
        if not path.is_file():
            log.warning("music missing, skip %s (%s)", name, path)
            return None
        return source_base(
            name,
            "ffmpeg_source",
            {
                "local_file": str(path.resolve()),
                "looping": True,
                "restart_on_activate": True,
                "close_when_inactive": True,
                "clear_on_media_end": False,
                "hw_decode": False,
                "speed_percent": 100,
                "is_local_file": True,
            },
            mixers=255,
            volume=volume,
        )

    # Beds only on interstitials (no game audio focus)
    mus_soon = music("Music Starting Soon", "starting-soon.mp3", volume=0.30)
    mus_brb = music("Music BRB", "brb.mp3", volume=0.26)
    mus_end = music("Music Ending", "ending.mp3", volume=0.28)

    def audio_bed_item(src: dict | None, item_id: int) -> list[dict]:
        """Tiny visible item so OBS keeps audio active (hidden sources mute media)."""
        if src is None:
            return []
        return [
            scene_item(
                src["name"],
                src["uuid"],
                item_id,
                pos=(-40.0, -40.0),
                scale=(0.001, 0.001),
                visible=True,
                locked=True,
                scale_ref=(1920.0, 1080.0),
            )
        ]

    # Webcam 560×315 inside cam chrome (left 36, bottom 36 on 1920×1080)
    cam_w, cam_h = 560.0, 315.0
    cam_scale = cam_w / 1920.0
    cam_x, cam_y = 36.0, CANVAS_H - 36.0 - cam_h
    cam_ref = (1920.0, 1080.0)

    # Smaller cam for interstitial scenes
    cam_sm_w = 280.0
    cam_sm_scale = cam_sm_w / 1920.0
    cam_sm_h = 1080.0 * cam_sm_scale
    cam_sm_x = (CANVAS_W - cam_sm_w) / 2.0
    cam_sm_y = CANVAS_H - 56.0 - cam_sm_h

    def fullscreen(name: str, source_uuid: str, item_id: int, *, visible: bool = True, locked: bool = False) -> dict:
        """Top-left full canvas item with correct OBS 32 relative transforms."""
        return scene_item(
            name,
            source_uuid,
            item_id,
            pos=(0.0, 0.0),
            scale=(1.0, 1.0),
            visible=visible,
            locked=locked,
            scale_ref=(float(CANVAS_W), float(CANVAS_H)),
        )

    scene_soon = make_scene(
        "Starting Soon",
        [
            fullscreen(ov_soon["name"], ov_soon["uuid"], 1, locked=True),
            scene_item(
                cam["name"],
                cam["uuid"],
                2,
                pos=(cam_sm_x, cam_sm_y),
                scale=(cam_sm_scale, cam_sm_scale),
                scale_ref=cam_ref,
            ),
            *audio_bed_item(mus_soon, 3),
        ],
    )
    scene_race = make_scene(
        "Live Race",
        [
            fullscreen(mon_center["name"], mon_center["uuid"], 1),
            scene_item(game["name"], game["uuid"], 2, visible=False),
            fullscreen(ov_live["name"], ov_live["uuid"], 3, locked=True),
            scene_item(
                cam["name"],
                cam["uuid"],
                4,
                pos=(cam_x, cam_y),
                scale=(cam_scale, cam_scale),
                scale_ref=cam_ref,
            ),
        ],
    )
    scene_single = make_scene(
        "Live Singolo",
        [
            fullscreen(mon_single["name"], mon_single["uuid"], 1),
            fullscreen(game["name"], game["uuid"], 2, visible=False),
            fullscreen(ov_live["name"], ov_live["uuid"], 3, locked=True),
            scene_item(
                cam["name"],
                cam["uuid"],
                4,
                pos=(cam_x, cam_y),
                scale=(cam_scale, cam_scale),
                scale_ref=cam_ref,
            ),
        ],
    )
    scene_brb = make_scene(
        "BRB",
        [
            fullscreen(ov_brb["name"], ov_brb["uuid"], 1, locked=True),
            scene_item(
                cam["name"],
                cam["uuid"],
                2,
                pos=(cam_sm_x, cam_sm_y),
                scale=(cam_sm_scale, cam_sm_scale),
                scale_ref=cam_ref,
            ),
            *audio_bed_item(mus_brb, 3),
        ],
    )
    scene_end = make_scene(
        "Ending",
        [
            fullscreen(ov_end["name"], ov_end["uuid"], 1, locked=True),
            *audio_bed_item(mus_end, 2),
        ],
    )
    # Recording layouts: clean (no overlay / no cam)
    scene_rec_single = make_scene(
        "Rec Singolo",
        [
            layout_single_monitor(
                mon_center["name"],
                mon_center["uuid"],
                1,
                roles["center"],
                visible=False,
                locked=True,
            ),
            fullscreen(game["name"], game["uuid"], 2, locked=True),
        ],
    )
    scene_rec_triple = make_scene(
        "Rec Triplo",
        [
            layout_iracing_window(
                game["name"], game["uuid"], 1, roles, locked=True
            ),
        ],
    )

    # Cam in the bottom graphic band CAM slot (matches .triple-cam-slot)
    cam_triple_x, cam_triple_y = triple_cam_pos()
    cam_triple_scale = _TRIPLE_CAM_W / 1920.0

    def items_stream_triple() -> list[dict]:
        """iRacing + letterbox brand + cam — for Live Triplo / Rec Triplo Live."""
        items = [layout_iracing_window(game["name"], game["uuid"], 1, roles)]
        next_id = 2
        frame_live = ov_triple_live or ov_triple
        if frame_live is not None:
            items.append(
                fullscreen(frame_live["name"], frame_live["uuid"], next_id, locked=True)
            )
            next_id += 1
        else:
            items.append(
                fullscreen(ov_live["name"], ov_live["uuid"], next_id, locked=True)
            )
            next_id += 1
        items.append(
            scene_item(
                cam["name"],
                cam["uuid"],
                next_id,
                pos=(cam_triple_x, cam_triple_y),
                scale=(cam_triple_scale, cam_triple_scale),
                scale_ref=cam_ref,
            )
        )
        return items

    # Streaming: Live* (with overlays + cam). Rec * Live kept as aliases.
    scene_live_triple = None
    if ov_triple is not None:
        scene_live_triple = make_scene("Live Triplo", items_stream_triple())

    scene_rec_single_live = make_scene(
        "Rec Singolo Live",
        [
            layout_single_monitor(
                mon_center["name"],
                mon_center["uuid"],
                1,
                roles["center"],
                visible=False,
            ),
            fullscreen(game["name"], game["uuid"], 2),
            fullscreen(ov_live["name"], ov_live["uuid"], 3, locked=True),
            scene_item(
                cam["name"],
                cam["uuid"],
                4,
                pos=(cam_x, cam_y),
                scale=(cam_scale, cam_scale),
                scale_ref=cam_ref,
            ),
        ],
    )
    scene_rec_triple_live = make_scene("Rec Triplo Live", items_stream_triple())

    # Attach scene uuids already set in make_scene; collect sources
    music_sources = [s for s in (mus_soon, mus_brb, mus_end) if s is not None]
    if music_sources:
        log.info("interstitial music beds: %s", ", ".join(s["name"] for s in music_sources))
    sources = [
        desktop,
        mic,
        cam,
        mon_left,
        mon_center,
        mon_right,
        mon_single,
        game,
        ov_soon,
        ov_brb,
        ov_end,
        ov_live,
        *([ov_triple] if ov_triple is not None else []),
        *([ov_triple_live] if ov_triple_live is not None else []),
        *music_sources,
        scene_soon,
        scene_race,
        scene_single,
        *([scene_live_triple] if scene_live_triple is not None else []),
        scene_rec_single,
        scene_rec_triple,
        scene_rec_single_live,
        scene_rec_triple_live,
        scene_brb,
        scene_end,
    ]

    scene_order = [
        {"name": "Starting Soon"},
        {"name": "Live Race"},
        {"name": "Live Singolo"},
    ]
    if scene_live_triple is not None:
        scene_order.append({"name": "Live Triplo"})
    scene_order.extend(
        [
            {"name": "Rec Singolo"},
            {"name": "Rec Triplo"},
            {"name": "Rec Singolo Live"},
            {"name": "Rec Triplo Live"},
            {"name": "BRB"},
            {"name": "Ending"},
        ]
    )

    collection = {
        "name": collection_name,
        "DesktopAudioDevice1": desktop,
        "AuxAudioDevice1": mic,
        "sources": sources,
        "groups": [],
        "scene_order": scene_order,
        "current_scene": "Starting Soon",
        "current_program_scene": "Starting Soon",
        "canvases": [],
        "current_transition": "Dissolvenza",
        "transition_duration": 300,
        "transitions": [],
        "quick_transitions": [],
        "saved_projectors": [],
        "preview_locked": False,
        "scaling_enabled": False,
        "scaling_level": 0,
        "scaling_off_x": 0.0,
        "scaling_off_y": 0.0,
        "modules": {
            "scripts-tool": config_autostart_scripts(),
            "auto-scene-switcher": {
                "interval": 300,
                "non_matching_scene": "",
                "switch_if_not_matching": False,
                "active": False,
                "switches": [],
            },
        },
        "resolution": {"x": CANVAS_W, "y": CANVAS_H},
        "version": 2,
    }

    # Desktop/Aux are also top-level; OBS expects them duplicated in sources sometimes.
    # Existing Streaming_Gaming keeps them only top-level AND also in sources list for scenes.
    # Looking at the file - DesktopAudioDevice1 is top-level only, scenes are in sources.
    # Audio devices are NOT in the sources array in the beginning... wait they might not be.
    # From the read: sources starts with avermedia, Browser, logitech - Desktop is top-level only.
    # So remove desktop/mic from sources array.
    collection["sources"] = [s for s in sources if s["name"] not in ("Audio Desktop", "Microfono")]

    transitions, current_tr, tr_dur = build_transitions(overlays_dir=overlays_dir, profile=profile)
    collection["transitions"] = transitions
    collection["current_transition"] = current_tr
    collection["transition_duration"] = tr_dur
    collection["quick_transitions"] = [
        {"name": "Taglio", "duration": 0, "hotkeys": [], "id": 1, "fade_to_black": False},
        {"name": current_tr, "duration": tr_dur, "hotkeys": [], "id": 2, "fade_to_black": False},
        {"name": "Swipe Racing", "duration": 420, "hotkeys": [], "id": 3, "fade_to_black": False},
        {"name": "Flash Carbon", "duration": 280, "hotkeys": [], "id": 4, "fade_to_black": False},
        {"name": "Dissolvenza", "duration": 350, "hotkeys": [], "id": 5, "fade_to_black": False},
    ]
    log.info("default transition=%s (%d ms), %d transitions", current_tr, tr_dur, len(transitions))

    out = OBS_DIR / output_filename
    out.write_text(json.dumps(collection, indent=4), encoding="utf-8")
    log.info(
        "scene collection written to %s (%d sources) in %.0f ms",
        out,
        len(collection["sources"]),
        (time.perf_counter() - t0) * 1000,
    )
    return out


def build_replay_collection(*, overlays: Path | None = None) -> Path:
    """Marcato collection for streaming an iRacing replay (or a video file) live."""
    t0 = time.perf_counter()
    overlays_dir = overlays or (ROOT / "overlays-marcato")
    OBS_DIR.mkdir(parents=True, exist_ok=True)
    replays_dir = ROOT / "replays"
    replays_dir.mkdir(parents=True, exist_ok=True)
    video_path = replays_dir / "race-replay.mp4"

    desktop = source_base(
        "Audio Desktop",
        "wasapi_output_capture",
        {"device_id": "default"},
        mixers=255,
        volume=0.55,
    )
    mic = source_base(
        "Microfono",
        "wasapi_input_capture",
        {"device_id": MIC_ID},
        mixers=255,
        volume=0.9,
    )
    # P1-04 dual cam + NVIDIA greenscreen (Quality+Chair) + carbon plate
    cam = dshow_cam("StreamCam", STREAMCAM_ID)
    cam2 = dshow_cam("Cam 2", USBCAM_ID)
    cam_bd_face = cam_carbon_backdrop(
        "Cam Backdrop Face", width=360, height=202, marcato=True
    )
    cam_bd_2 = cam_carbon_backdrop(
        "Cam Backdrop 2", width=320, height=180, marcato=True
    )
    roles = monitor_roles()
    for role, mon in roles.items():
        if mon:
            log.info(
                "replay monitor %s: %s %dx%d @%d,%d",
                role,
                mon.get("device"),
                mon["w"],
                mon["h"],
                mon["x"],
                mon["y"],
            )
    mon_left = source_base(
        "Monitor Sinistro",
        "monitor_capture",
        monitor_capture_settings(roles["left"]),
    )
    mon_center = source_base(
        "Monitor Centro",
        "monitor_capture",
        monitor_capture_settings(roles["center"]),
    )
    mon_right = source_base(
        "Monitor Destro",
        "monitor_capture",
        monitor_capture_settings(roles["right"]),
    )
    game = source_base(
        "Game Capture",
        "game_capture",
        iracing_capture_settings(),
        mixers=255,
    )
    # Only wire Race Video when the file exists — avoids OBS "file missing" dialog.
    race_video: dict | None = None
    if video_path.is_file():
        race_video = source_base(
            "Race Video",
            "ffmpeg_source",
            {
                "local_file": str(video_path.resolve()),
                "looping": False,
                "restart_on_activate": True,
                "close_when_inactive": False,
                "clear_on_media_end": False,
                "hw_decode": True,
                "speed_percent": 100,
                "is_local_file": True,
            },
            mixers=255,
            volume=0.85,
        )
        log.info("Race Video source: %s", video_path.name)
    else:
        log.info(
            "no %s yet — skip Replay Video scene (use iRacing .rpy or drop an mp4 later)",
            video_path.name,
        )

    def browser(name: str, html: str, *, query: str = "") -> dict:
        url = file_url(overlays_dir / html)
        if query:
            url = f"{url}?{query.lstrip('?')}"
        return source_base(
            name,
            "browser_source",
            {
                "url": url,
                "width": CANVAS_W,
                "height": CANVAS_H,
                "fps": 30,
                "shutdown": True,
                "restart_when_active": True,
                "webpage_control_level": 1,
            },
        )

    ov_soon = browser("Overlay Starting Soon", "starting-soon.html")
    ov_brb = browser("Overlay BRB", "brb.html")
    ov_end = browser("Overlay Ending", "ending.html")
    # cam=0: riquadro CAM non duplicato (sta nella nested scene Cam PIP)
    ov_replay = browser("Overlay Replay Chrome", "replay-chrome.html", query="cam=0")
    # Telecronaca (P3-02): HTTP URL so OBS CEF can open the telemetry WebSocket
    ov_broadcast = source_base(
        "Overlay Broadcast Chrome",
        "browser_source",
        {
            "url": overlay_http_url(overlays_dir, "broadcast-chrome.html"),
            "width": CANVAS_W,
            "height": CANVAS_H,
            "fps": 30,
            "shutdown": True,
            "restart_when_active": True,
            "webpage_control_level": 1,
        },
    )
    ov_cam_frame = browser("Overlay Cam Frame", "cam-frame.html")
    ov_cam_frame_2 = browser("Overlay Cam 2 Frame", "cam-frame-2.html")
    ov_triple = browser("Overlay Triple Frame", "triple-frame.html", query="badge=REPLAY")
    ov_triple_live = browser(
        "Overlay Triple Frame Live",
        "triple-frame.html",
        query="cam=1&badge=REPLAY",
    )

    def music(name: str, filename: str, *, volume: float = 0.28) -> dict | None:
        path = AUDIO_DIR / filename
        if not path.is_file():
            return None
        return source_base(
            name,
            "ffmpeg_source",
            {
                "local_file": str(path.resolve()),
                "looping": True,
                "restart_on_activate": True,
                "close_when_inactive": True,
                "clear_on_media_end": False,
                "hw_decode": False,
                "speed_percent": 100,
                "is_local_file": True,
            },
            mixers=255,
            volume=volume,
        )

    mus_soon = music("Music Starting Soon", "starting-soon.mp3", volume=0.30)
    mus_brb = music("Music BRB", "brb.mp3", volume=0.26)
    mus_end = music("Music Ending", "ending.mp3", volume=0.28)

    def audio_bed_item(src: dict | None, item_id: int) -> list[dict]:
        if src is None:
            return []
        return [
            scene_item(
                src["name"],
                src["uuid"],
                item_id,
                pos=(-40.0, -40.0),
                scale=(0.001, 0.001),
                visible=True,
                locked=True,
                scale_ref=(1920.0, 1080.0),
            )
        ]

    cam_w, cam_h = 360.0, 202.0
    cam_scale = cam_w / 1920.0
    cam_x, cam_y = 36.0, CANVAS_H - 36.0 - cam_h
    cam_ref = (1920.0, 1080.0)
    cam2_w, cam2_h = 320.0, 180.0
    cam2_scale = cam2_w / 1920.0
    cam2_x, cam2_y = CANVAS_W - 36.0 - cam2_w, CANVAS_H - 36.0 - cam2_h
    cam_sm_w = 280.0
    cam_sm_scale = cam_sm_w / 1920.0
    cam_sm_h = 1080.0 * cam_sm_scale
    cam_sm_x = (CANVAS_W - cam_sm_w) / 2.0
    cam_sm_y = CANVAS_H - 56.0 - cam_sm_h
    cam_triple_x, cam_triple_y = triple_cam_pos()
    cam_triple_scale = _TRIPLE_CAM_W / 1920.0

    def fullscreen(
        name: str,
        source_uuid: str,
        item_id: int,
        *,
        visible: bool = True,
        locked: bool = False,
    ) -> dict:
        return scene_item(
            name,
            source_uuid,
            item_id,
            pos=(0.0, 0.0),
            scale=(1.0, 1.0),
            visible=visible,
            locked=locked,
            scale_ref=(float(CANVAS_W), float(CANVAS_H)),
        )

    def cam_pip(item_id: int, *, small: bool = False) -> dict:
        if small:
            return scene_item(
                cam["name"],
                cam["uuid"],
                item_id,
                pos=(cam_sm_x, cam_sm_y),
                scale=(cam_sm_scale, cam_sm_scale),
                scale_ref=cam_ref,
            )
        return scene_item(
            cam["name"],
            cam["uuid"],
            item_id,
            pos=(cam_x, cam_y),
            scale=(cam_scale, cam_scale),
            scale_ref=cam_ref,
        )

    # Nested: carbon plate + NVIDIA greenscreen cam + frame
    scene_cam_pip = make_scene(
        "Cam PIP",
        [
            scene_item(
                cam_bd_face["name"],
                cam_bd_face["uuid"],
                1,
                pos=(cam_x, cam_y),
                scale=(1.0, 1.0),
                scale_ref=(cam_w, cam_h),
                locked=True,
            ),
            scene_item(
                cam["name"],
                cam["uuid"],
                2,
                pos=(cam_x, cam_y),
                scale=(cam_scale, cam_scale),
                scale_ref=cam_ref,
            ),
            fullscreen(ov_cam_frame["name"], ov_cam_frame["uuid"], 3, locked=True),
        ],
    )
    scene_cam2_pip = make_scene(
        "Cam 2 PIP",
        [
            scene_item(
                cam_bd_2["name"],
                cam_bd_2["uuid"],
                1,
                pos=(cam2_x, cam2_y),
                scale=(1.0, 1.0),
                scale_ref=(cam2_w, cam2_h),
                locked=True,
            ),
            scene_item(
                cam2["name"],
                cam2["uuid"],
                2,
                pos=(cam2_x, cam2_y),
                scale=(cam2_scale, cam2_scale),
                scale_ref=cam_ref,
            ),
            fullscreen(ov_cam_frame_2["name"], ov_cam_frame_2["uuid"], 3, locked=True),
        ],
    )

    def cam_pip_optional(item_id: int, *, visible: bool = True) -> dict:
        """Optional face-cam block (webcam + CAM frame) for replay commentary scenes."""
        return scene_item(
            scene_cam_pip["name"],
            scene_cam_pip["uuid"],
            item_id,
            pos=(0.0, 0.0),
            scale=(1.0, 1.0),
            visible=visible,
            scale_ref=(float(CANVAS_W), float(CANVAS_H)),
        )

    def cam2_pip_optional(item_id: int, *, visible: bool = True) -> dict:
        """Optional seat/wide cam (bottom-right) with virtual carbon BG."""
        return scene_item(
            scene_cam2_pip["name"],
            scene_cam2_pip["uuid"],
            item_id,
            pos=(0.0, 0.0),
            scale=(1.0, 1.0),
            visible=visible,
            scale_ref=(float(CANVAS_W), float(CANVAS_H)),
        )

    scene_soon = make_scene(
        "Starting Soon",
        [
            fullscreen(ov_soon["name"], ov_soon["uuid"], 1, locked=True),
            cam_pip(2, small=True),
            *audio_bed_item(mus_soon, 3),
        ],
    )
    scene_iracing = make_scene(
        "Replay iRacing",
        [
            fullscreen(mon_center["name"], mon_center["uuid"], 1, visible=False),
            fullscreen(game["name"], game["uuid"], 2),
            fullscreen(ov_replay["name"], ov_replay["uuid"], 3, locked=True),
            fullscreen(
                ov_broadcast["name"], ov_broadcast["uuid"], 4, visible=False, locked=True
            ),
            cam_pip_optional(5, visible=True),
            cam2_pip_optional(6, visible=True),
        ],
    )
    scene_monitor = make_scene(
        "Replay Monitor",
        [
            layout_single_monitor(
                mon_center["name"], mon_center["uuid"], 1, roles["center"]
            ),
            fullscreen(game["name"], game["uuid"], 2, visible=False),
            fullscreen(ov_replay["name"], ov_replay["uuid"], 3, locked=True),
            fullscreen(
                ov_broadcast["name"], ov_broadcast["uuid"], 4, visible=False, locked=True
            ),
            cam_pip_optional(5, visible=True),
            cam2_pip_optional(6, visible=True),
        ],
    )
    scene_video = None
    if race_video is not None:
        scene_video = make_scene(
            "Replay Video",
            [
                fullscreen(race_video["name"], race_video["uuid"], 1),
                fullscreen(ov_replay["name"], ov_replay["uuid"], 2, locked=True),
                fullscreen(
                    ov_broadcast["name"],
                    ov_broadcast["uuid"],
                    3,
                    visible=False,
                    locked=True,
                ),
                cam_pip_optional(4, visible=True),
                cam2_pip_optional(5, visible=True),
            ],
        )

    def items_replay_triple() -> list[dict]:
        """iRacing + letterbox brand (REPLAY) + optional cam in bottom band."""
        return [
            layout_iracing_window(game["name"], game["uuid"], 1, roles),
            fullscreen(ov_triple_live["name"], ov_triple_live["uuid"], 2, locked=True),
            scene_item(
                cam["name"],
                cam["uuid"],
                3,
                pos=(cam_triple_x, cam_triple_y),
                scale=(cam_triple_scale, cam_triple_scale),
                scale_ref=cam_ref,
                visible=True,
            ),
        ]

    # Recording: clean (no overlay / no cam)
    scene_rec_single = make_scene(
        "Rec Singolo",
        [
            layout_single_monitor(
                mon_center["name"],
                mon_center["uuid"],
                1,
                roles["center"],
                visible=False,
                locked=True,
            ),
            fullscreen(game["name"], game["uuid"], 2, locked=True),
        ],
    )
    scene_rec_triple = make_scene(
        "Rec Triplo",
        [
            layout_iracing_window(
                game["name"], game["uuid"], 1, roles, locked=True
            ),
        ],
    )
    scene_rec_single_live = make_scene(
        "Rec Singolo Live",
        [
            layout_single_monitor(
                mon_center["name"], mon_center["uuid"], 1, roles["center"], visible=False
            ),
            fullscreen(game["name"], game["uuid"], 2),
            fullscreen(ov_replay["name"], ov_replay["uuid"], 3, locked=True),
            fullscreen(
                ov_broadcast["name"], ov_broadcast["uuid"], 4, visible=False, locked=True
            ),
            cam_pip_optional(5, visible=True),
            cam2_pip_optional(6, visible=True),
        ],
    )
    scene_rec_triple_live = make_scene(
        "Rec Triplo Live",
        [
            *items_replay_triple(),
            fullscreen(
                ov_broadcast["name"], ov_broadcast["uuid"], 4, visible=False, locked=True
            ),
        ],
    )
    scene_brb = make_scene(
        "BRB",
        [
            fullscreen(ov_brb["name"], ov_brb["uuid"], 1, locked=True),
            cam_pip(2, small=True),
            *audio_bed_item(mus_brb, 3),
        ],
    )
    scene_end = make_scene(
        "Ending",
        [
            fullscreen(ov_end["name"], ov_end["uuid"], 1, locked=True),
            *audio_bed_item(mus_end, 2),
        ],
    )

    music_sources = [s for s in (mus_soon, mus_brb, mus_end) if s is not None]
    sources = [
        cam,
        cam2,
        cam_bd_face,
        cam_bd_2,
        mon_left,
        mon_center,
        mon_right,
        game,
        *([race_video] if race_video is not None else []),
        ov_soon,
        ov_brb,
        ov_end,
        ov_replay,
        ov_broadcast,
        ov_cam_frame,
        ov_cam_frame_2,
        ov_triple,
        ov_triple_live,
        *music_sources,
        scene_cam_pip,
        scene_cam2_pip,
        scene_soon,
        scene_iracing,
        scene_monitor,
        *([scene_video] if scene_video is not None else []),
        scene_rec_single,
        scene_rec_triple,
        scene_rec_single_live,
        scene_rec_triple_live,
        scene_brb,
        scene_end,
    ]

    scene_order = [
        {"name": "Starting Soon"},
        {"name": "Replay iRacing"},
        {"name": "Replay Monitor"},
    ]
    if scene_video is not None:
        scene_order.append({"name": "Replay Video"})
    scene_order.extend(
        [
            {"name": "Rec Singolo"},
            {"name": "Rec Triplo"},
            {"name": "Rec Singolo Live"},
            {"name": "Rec Triplo Live"},
            {"name": "BRB"},
            {"name": "Ending"},
        ]
    )

    collection = {
        "name": "S.Marcato Replay",
        "DesktopAudioDevice1": desktop,
        "AuxAudioDevice1": mic,
        "sources": sources,
        "groups": [],
        "scene_order": scene_order,
        "current_scene": "Starting Soon",
        "current_program_scene": "Starting Soon",
        "canvases": [],
        "current_transition": "Dissolvenza",
        "transition_duration": 300,
        "transitions": [],
        "quick_transitions": [],
        "saved_projectors": [],
        "preview_locked": False,
        "scaling_enabled": False,
        "scaling_level": 0,
        "scaling_off_x": 0.0,
        "scaling_off_y": 0.0,
        "modules": {
            "scripts-tool": config_autostart_scripts(),
            "auto-scene-switcher": {
                "interval": 300,
                "non_matching_scene": "",
                "switch_if_not_matching": False,
                "active": False,
                "switches": [],
            },
        },
        "resolution": {"x": CANVAS_W, "y": CANVAS_H},
        "version": 2,
    }

    transitions, current_tr, tr_dur = build_transitions(
        overlays_dir=overlays_dir, profile="marcato"
    )
    collection["transitions"] = transitions
    collection["current_transition"] = current_tr
    collection["transition_duration"] = tr_dur
    collection["quick_transitions"] = [
        {"name": "Taglio", "duration": 0, "hotkeys": [], "id": 1, "fade_to_black": False},
        {"name": current_tr, "duration": tr_dur, "hotkeys": [], "id": 2, "fade_to_black": False},
        {"name": "Dissolvenza", "duration": 350, "hotkeys": [], "id": 3, "fade_to_black": False},
    ]

    out = OBS_DIR / "S_Marcato_Replay.json"
    out.write_text(json.dumps(collection, indent=4), encoding="utf-8")
    log.info(
        "replay collection written to %s (%d sources) in %.0f ms",
        out,
        len(collection["sources"]),
        (time.perf_counter() - t0) * 1000,
    )
    return out


def build_rec_2k_collection(*, overlays: Path | None = None) -> Path:
    """Marcato recording pack at 2560×1440 with brand overlays (ADR-007).

    Overlay HTML stays designed at 1920×1080; Browser Sources are scaled by
    4/3 onto the 2K canvas so graphics match the stream pack.
    """
    t0 = time.perf_counter()
    overlays_dir = Path(overlays) if overlays else ROOT / "overlays-marcato"
    roles = monitor_roles()
    for label in ("left", "center", "right"):
        mon = roles.get(label)
        if mon:
            log.info(
                "rec2k monitor %s: %s %dx%d @%d,%d",
                label,
                mon.get("device") or mon.get("monitor_id") or "?",
                mon["w"],
                mon["h"],
                mon["x"],
                mon["y"],
            )
        else:
            log.warning("rec2k monitor %s not detected — pick display in OBS", label)

    design_w, design_h = 1920.0, 1080.0
    scale_2k = REC_2K_W / design_w  # 4/3

    with canvas_context(REC_2K_W, REC_2K_H, canvas_uuid=CANVAS_UUID_2K):
        desktop = source_base(
            "Desktop Audio",
            "wasapi_output_capture",
            {"device_id": "default"},
            mixers=1,
        )
        mic = source_base(
            "Mic/Aux",
            "wasapi_input_capture",
            {"device_id": MIC_ID},
            mixers=2,
        )
        cam = dshow_cam("StreamCam", STREAMCAM_ID)
        cam2 = dshow_cam("Cam 2", USBCAM_ID)
        cam_bd_face = cam_carbon_backdrop(
            "Cam Backdrop Face", width=360, height=202, marcato=True
        )
        cam_bd_2 = cam_carbon_backdrop(
            "Cam Backdrop 2", width=320, height=180, marcato=True
        )
        mon_center = source_base(
            "Monitor Centrale",
            "monitor_capture",
            monitor_capture_settings(roles["center"]),
        )
        game = source_base("Game Capture", "game_capture", iracing_capture_settings())

        def browser(name: str, html: str, *, query: str = "") -> dict:
            path = overlays_dir / html
            url = file_url(path)
            if query:
                url = f"{url}?{query}"
            return source_base(
                name,
                "browser_source",
                {
                    "url": url,
                    "width": int(design_w),
                    "height": int(design_h),
                    "fps": 30,
                    "shutdown": True,
                    "restart_when_active": True,
                    "webpage_control_level": 1,
                },
            )

        ov_live = browser("Overlay Live Chrome", "live-chrome.html")
        ov_broadcast = source_base(
            "Overlay Broadcast Chrome",
            "browser_source",
            {
                "url": overlay_http_url(overlays_dir, "broadcast-chrome.html"),
                "width": int(design_w),
                "height": int(design_h),
                "fps": 30,
                "shutdown": True,
                "restart_when_active": True,
                "webpage_control_level": 1,
            },
        )
        ov_triple_live = browser(
            "Overlay Triple Frame Live",
            "triple-frame.html",
            query="cam=1&badge=LIVE",
        )
        ov_cam_frame = browser("Overlay Cam Frame", "cam-frame.html")
        ov_cam_frame_2 = browser("Overlay Cam 2 Frame", "cam-frame-2.html")

        def overlay_fs(src: dict, item_id: int, *, locked: bool = True) -> dict:
            """Place a 1920×1080 browser so it fills the 2K canvas."""
            return scene_item(
                src["name"],
                src["uuid"],
                item_id,
                pos=(0.0, 0.0),
                scale=(scale_2k, scale_2k),
                locked=locked,
                scale_ref=(design_w, design_h),
            )

        # Build Cam PIP nests in 1080 design space, then scale onto 2K canvas
        cam_w1080, cam_h1080 = 360.0, 202.0
        cam_x1080, cam_y1080 = 36.0, 1080.0 - 36.0 - cam_h1080
        cam2_w1080, cam2_h1080 = 320.0, 180.0
        cam2_x1080 = 1920.0 - 36.0 - cam2_w1080
        cam2_y1080 = 1080.0 - 36.0 - cam2_h1080
        with canvas_context(1920, 1080):
            scene_cam_pip = make_scene(
                "Cam PIP",
                [
                    scene_item(
                        cam_bd_face["name"],
                        cam_bd_face["uuid"],
                        1,
                        pos=(cam_x1080, cam_y1080),
                        scale=(1.0, 1.0),
                        scale_ref=(cam_w1080, cam_h1080),
                        locked=True,
                    ),
                    scene_item(
                        cam["name"],
                        cam["uuid"],
                        2,
                        pos=(cam_x1080, cam_y1080),
                        scale=(cam_w1080 / 1920.0, cam_w1080 / 1920.0),
                        scale_ref=(1920.0, 1080.0),
                    ),
                    scene_item(
                        ov_cam_frame["name"],
                        ov_cam_frame["uuid"],
                        3,
                        pos=(0.0, 0.0),
                        scale=(1.0, 1.0),
                        locked=True,
                        scale_ref=(1920.0, 1080.0),
                    ),
                ],
            )
            scene_cam2_pip = make_scene(
                "Cam 2 PIP",
                [
                    scene_item(
                        cam_bd_2["name"],
                        cam_bd_2["uuid"],
                        1,
                        pos=(cam2_x1080, cam2_y1080),
                        scale=(1.0, 1.0),
                        scale_ref=(cam2_w1080, cam2_h1080),
                        locked=True,
                    ),
                    scene_item(
                        cam2["name"],
                        cam2["uuid"],
                        2,
                        pos=(cam2_x1080, cam2_y1080),
                        scale=(cam2_w1080 / 1920.0, cam2_w1080 / 1920.0),
                        scale_ref=(1920.0, 1080.0),
                    ),
                    scene_item(
                        ov_cam_frame_2["name"],
                        ov_cam_frame_2["uuid"],
                        3,
                        pos=(0.0, 0.0),
                        scale=(1.0, 1.0),
                        locked=True,
                        scale_ref=(1920.0, 1080.0),
                    ),
                ],
            )

        def cam_pip_item(item_id: int, *, visible: bool = True) -> dict:
            return scene_item(
                scene_cam_pip["name"],
                scene_cam_pip["uuid"],
                item_id,
                pos=(0.0, 0.0),
                scale=(scale_2k, scale_2k),
                scale_ref=(design_w, design_h),
                visible=visible,
            )

        def cam2_pip_item(item_id: int, *, visible: bool = True) -> dict:
            return scene_item(
                scene_cam2_pip["name"],
                scene_cam2_pip["uuid"],
                item_id,
                pos=(0.0, 0.0),
                scale=(scale_2k, scale_2k),
                scale_ref=(design_w, design_h),
                visible=visible,
            )

        # Design-space triple cam slot (1080 pack) → scaled to 2K
        triple_cam_x_1080 = (
            (design_w - _TRIPLE_INNER_W) / 2.0 + _TRIPLE_INNER_W - _TRIPLE_CAM_W
        )
        triple_band_1080 = (design_h - _TRIPLE_SAFE_H) / 2.0
        triple_cam_y_1080 = (
            design_h
            - triple_band_1080
            + max(0.0, (triple_band_1080 - _TRIPLE_CAM_H) / 2.0)
        )

        def cam_triple_item(item_id: int, *, visible: bool = True) -> dict:
            # Face cam only in triple band; Cam 2 stays optional PIP
            cam_w = _TRIPLE_CAM_W * scale_2k
            return scene_item(
                cam["name"],
                cam["uuid"],
                item_id,
                pos=(triple_cam_x_1080 * scale_2k, triple_cam_y_1080 * scale_2k),
                scale=(cam_w / 1920.0, cam_w / 1920.0),
                scale_ref=(1920.0, 1080.0),
                visible=visible,
            )

        def game_triple_live_item(item_id: int) -> dict:
            band_h = _TRIPLE_SAFE_H * scale_2k
            band_y = triple_band_1080 * scale_2k
            item = scene_item(
                game["name"],
                game["uuid"],
                item_id,
                pos=(0.0, band_y),
                scale=(1.0, 1.0),
                scale_ref=(float(CANVAS_W), float(CANVAS_H)),
                bounds=(float(CANVAS_W), band_h),
                bounds_type=_BOUNDS_SCALE_OUTER,
            )
            item["bounds_crop"] = True
            return item

        # Clean recording (no graphics)
        scene_rec_single = make_scene(
            "Rec Singolo",
            [
                layout_single_monitor(
                    mon_center["name"],
                    mon_center["uuid"],
                    1,
                    roles["center"],
                    visible=False,
                    locked=True,
                ),
                scene_item(
                    game["name"],
                    game["uuid"],
                    2,
                    pos=(0.0, 0.0),
                    scale=(1.0, 1.0),
                    locked=True,
                    scale_ref=(float(CANVAS_W), float(CANVAS_H)),
                    bounds=(float(CANVAS_W), float(CANVAS_H)),
                    bounds_type=_BOUNDS_SCALE_OUTER,
                ),
            ],
        )
        scene_rec_single["settings"]["items"][1]["bounds_crop"] = True
        scene_rec_triple = make_scene(
            "Rec Triplo",
            [
                scene_item(
                    game["name"],
                    game["uuid"],
                    1,
                    pos=(0.0, 0.0),
                    scale=(1.0, 1.0),
                    locked=True,
                    scale_ref=(float(CANVAS_W), float(CANVAS_H)),
                    bounds=(float(CANVAS_W), float(CANVAS_H)),
                    bounds_type=_BOUNDS_SCALE_OUTER,
                ),
            ],
        )
        scene_rec_triple["settings"]["items"][0]["bounds_crop"] = True

        # With brand graphics + optional StreamCam (eye).
        # Lua sync: StreamCam hidden → overlay ?cam=0 → lower-third bottom-left.
        # Game Capture primary; Monitor Centrale as eye-toggle fallback.
        scene_rec_single_live = make_scene(
            "Rec Singolo Live",
            [
                layout_single_monitor(
                    mon_center["name"],
                    mon_center["uuid"],
                    1,
                    roles["center"],
                    visible=False,
                ),
                scene_item(
                    game["name"],
                    game["uuid"],
                    2,
                    pos=(0.0, 0.0),
                    scale=(1.0, 1.0),
                    scale_ref=(float(CANVAS_W), float(CANVAS_H)),
                    bounds=(float(CANVAS_W), float(CANVAS_H)),
                    bounds_type=_BOUNDS_SCALE_OUTER,
                ),
                overlay_fs(ov_live, 3),
                scene_item(
                    ov_broadcast["name"],
                    ov_broadcast["uuid"],
                    4,
                    pos=(0.0, 0.0),
                    scale=(scale_2k, scale_2k),
                    locked=True,
                    visible=False,
                    scale_ref=(design_w, design_h),
                ),
                cam_pip_item(5, visible=True),
                cam2_pip_item(6, visible=True),
            ],
        )
        scene_rec_single_live["settings"]["items"][1]["bounds_crop"] = True
        scene_rec_triple_live = make_scene(
            "Rec Triplo Live",
            [
                game_triple_live_item(1),
                overlay_fs(ov_triple_live, 2),
                scene_item(
                    ov_broadcast["name"],
                    ov_broadcast["uuid"],
                    3,
                    pos=(0.0, 0.0),
                    scale=(scale_2k, scale_2k),
                    locked=True,
                    visible=False,
                    scale_ref=(design_w, design_h),
                ),
                cam_triple_item(4, visible=True),
                cam2_pip_item(5, visible=True),
            ],
        )

        sources = [
            cam,
            cam2,
            cam_bd_face,
            cam_bd_2,
            mon_center,
            game,
            ov_live,
            ov_broadcast,
            ov_triple_live,
            ov_cam_frame,
            ov_cam_frame_2,
            scene_cam_pip,
            scene_cam2_pip,
            scene_rec_single,
            scene_rec_triple,
            scene_rec_single_live,
            scene_rec_triple_live,
        ]
        collection = {
            "name": "S.Marcato Rec 2K",
            "DesktopAudioDevice1": desktop,
            "AuxAudioDevice1": mic,
            "sources": sources,
            "groups": [],
            "scene_order": [
                {"name": "Rec Singolo"},
                {"name": "Rec Triplo"},
                {"name": "Rec Singolo Live"},
                {"name": "Rec Triplo Live"},
            ],
            "current_scene": "Rec Singolo Live",
            "current_program_scene": "Rec Singolo Live",
            "canvases": [],
            "current_transition": "Dissolvenza",
            "transition_duration": 300,
            "transitions": [],
            "quick_transitions": [
                {
                    "name": "Taglio",
                    "duration": 0,
                    "hotkeys": [],
                    "id": 1,
                    "fade_to_black": False,
                },
                {
                    "name": "Dissolvenza",
                    "duration": 300,
                    "hotkeys": [],
                    "id": 2,
                    "fade_to_black": False,
                },
            ],
            "saved_projectors": [],
            "preview_locked": False,
            "scaling_enabled": False,
            "scaling_level": 0,
            "scaling_off_x": 0.0,
            "scaling_off_y": 0.0,
            "modules": {
                "scripts-tool": config_autostart_scripts(),
                "auto-scene-switcher": {
                    "interval": 300,
                    "non_matching_scene": "",
                    "switch_if_not_matching": False,
                    "active": False,
                    "switches": [],
                },
            },
            "resolution": {"x": CANVAS_W, "y": CANVAS_H},
            "version": 2,
        }

        out = OBS_DIR / "S_Marcato_Rec_2K.json"
        out.write_text(json.dumps(collection, indent=4), encoding="utf-8")
        log.info(
            "rec 2K collection written to %s (%d sources, %dx%d, overlays scaled ×%.3f) in %.0f ms",
            out,
            len(collection["sources"]),
            CANVAS_W,
            CANVAS_H,
            scale_2k,
            (time.perf_counter() - t0) * 1000,
        )
        return out


def install_rec_2k_profile() -> Path:
    """Copy obs/profiles/Rec_2K into %APPDATA%/obs-studio/basic/profiles/."""
    src = OBS_DIR / "profiles" / "Rec_2K"
    dest = Path.home() / "AppData/Roaming/obs-studio/basic/profiles/Rec_2K"
    if not src.is_dir():
        raise FileNotFoundError(src)
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("basic.ini", "recordEncoder.json", "streamEncoder.json"):
        f = src / name
        if f.is_file():
            (dest / name).write_bytes(f.read_bytes())
    # Prefer user's Videos folder when present
    videos = Path.home() / "Videos"
    ini = dest / "basic.ini"
    if videos.is_dir() and ini.is_file():
        text = ini.read_text(encoding="utf-8")
        text = text.replace("C:\\\\Users\\\\Public\\\\Videos", str(videos).replace("\\", "\\\\"))
        ini.write_text(text, encoding="utf-8")
    log.info("OBS profile installed: %s", dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate OBS scene collection and optional logo PNG.")
    parser.add_argument(
        "--profile",
        choices=("pigreco", "marcato"),
        default="pigreco",
        help="pigreco: PiGreco_Racing.json + logo sync; marcato: S_Marcato_42 + Replay + Rec 2K",
    )
    parser.add_argument(
        "--install-rec-2k-profile",
        action="store_true",
        help="Copy obs/profiles/Rec_2K into OBS AppData profiles",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    logo_name = "skipped"
    outputs: list[str] = []

    if args.profile == "marcato":
        log.info("start generating S.Marcato 42 OBS collection (marcato profile)")
        scene = build_collection(
            overlays=ROOT / "overlays-marcato",
            collection_name="S.Marcato 42",
            output_filename="S_Marcato_42.json",
            profile="marcato",
        )
        outputs.append(scene.name)
        replay = build_replay_collection(overlays=ROOT / "overlays-marcato")
        outputs.append(replay.name)
        rec2k = build_rec_2k_collection(overlays=ROOT / "overlays-marcato")
        outputs.append(rec2k.name)
        install_rec_2k_profile()
    else:
        log.info("start generating PiGreco OBS pack")
        ASSETS.mkdir(parents=True, exist_ok=True)
        logo = export_logo_png()
        logo_name = logo.name
        scene = build_collection(profile="pigreco")
        outputs.append(scene.name)

    if args.install_rec_2k_profile and args.profile != "marcato":
        install_rec_2k_profile()

    elapsed = (time.perf_counter() - started) * 1000
    log.info(
        "done in %.0f ms | logo=%s | collection=%s",
        elapsed,
        logo_name,
        ", ".join(outputs),
    )


if __name__ == "__main__":
    main()
