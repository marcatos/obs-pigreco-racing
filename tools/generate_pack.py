"""Generate logo PNG and OBS scene collection for PiGreco Racing."""
from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
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

# Match OBS base canvas + stream output (1920x1080)
CANVAS_W = 1920
CANVAS_H = 1080

STREAMCAM_ID = (
    r"Logitech StreamCam:\\?\usb#22vid_046d&pid_0893&mi_00#228&33ee287c&0&0000"
    r"#22{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
)
MIC_ID = "{0.0.1.00000000}.{0679eb69-e8f9-4599-80e1-eef13c5d18e6}"
PREV_VER = 536936450
CANVAS_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def new_uuid() -> str:
    return str(uuid.uuid4())


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


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


def source_base(name: str, source_id: str, settings: dict, *, mixers: int = 0, volume: float = 1.0) -> dict:
    return {
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


def pos_rel(pos: tuple[float, float]) -> dict[str, float]:
    """OBS 28+ relative position (matches Streaming_Gaming / OBS 32.2)."""
    x, y = pos
    return {
        "x": (2.0 * x - CANVAS_W) / CANVAS_H,
        "y": (2.0 * y - CANVAS_H) / CANVAS_H,
    }


def scale_rel(scale: tuple[float, float], scale_ref: tuple[float, float]) -> dict[str, float]:
    return {
        "x": scale[0] * scale_ref[0] / CANVAS_W,
        "y": scale[1] * scale_ref[1] / CANVAS_H,
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
) -> dict:
    ref = scale_ref or (float(CANVAS_W), float(CANVAS_H))
    return {
        "name": name,
        "source_uuid": source_uuid,
        "visible": visible,
        "locked": locked,
        "rot": 0.0,
        "scale_ref": {"x": ref[0], "y": ref[1]},
        "align": 5,  # OBS_ALIGN_LEFT | OBS_ALIGN_TOP
        "bounds_type": 0,
        "bounds_align": 0,
        "bounds_crop": False,
        "crop_left": 0,
        "crop_top": 0,
        "crop_right": 0,
        "crop_bottom": 0,
        "id": item_id,
        "group_item_backup": False,
        "pos": {"x": float(pos[0]), "y": float(pos[1])},
        "pos_rel": pos_rel(pos),
        "scale": {"x": float(scale[0]), "y": float(scale[1])},
        "scale_rel": scale_rel(scale, ref),
        "bounds": {"x": 0.0, "y": 0.0},
        "bounds_rel": {"x": 0.0, "y": 0.0},
        "scale_filter": "disable",
        "blend_method": "default",
        "blend_type": "normal",
        "show_transition": {"duration": 300},
        "hide_transition": {"duration": 300},
        "private_settings": {},
    }


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
    cam = source_base(
        "StreamCam",
        "dshow_input",
        {
            "video_device_id": STREAMCAM_ID,
            "last_video_device_id": STREAMCAM_ID,
            "res_type": 1,
            "resolution": "1920x1080",
        },
        mixers=0,
    )
    mon_center = source_base(
        "Monitor Centro",
        "monitor_capture",
        {"capture_cursor": False, "method": 0},
    )
    mon_single = source_base(
        "Monitor Singolo",
        "monitor_capture",
        {"capture_cursor": False, "method": 0},
    )
    game = source_base(
        "Game Capture",
        "game_capture",
        {
            "capture_mode": "any_fullscreen",
            "priority": 2,
            "capture_cursor": False,
        },
    )

    def browser(name: str, html: str) -> dict:
        return source_base(
            name,
            "browser_source",
            {
                "url": file_url(overlays_dir / html),
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

    # Webcam ~360x202 inside cam frame (left 36, bottom 36 on 1920x1080)
    cam_w, cam_h = 360.0, 202.0
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
            fullscreen(ov_live["name"], ov_live["uuid"], 2, locked=True),
            scene_item(
                cam["name"],
                cam["uuid"],
                3,
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

    # Attach scene uuids already set in make_scene; collect sources
    music_sources = [s for s in (mus_soon, mus_brb, mus_end) if s is not None]
    if music_sources:
        log.info("interstitial music beds: %s", ", ".join(s["name"] for s in music_sources))
    sources = [
        desktop,
        mic,
        cam,
        mon_center,
        mon_single,
        game,
        ov_soon,
        ov_brb,
        ov_end,
        ov_live,
        *music_sources,
        scene_soon,
        scene_race,
        scene_single,
        scene_brb,
        scene_end,
    ]

    collection = {
        "name": collection_name,
        "DesktopAudioDevice1": desktop,
        "AuxAudioDevice1": mic,
        "sources": sources,
        "groups": [],
        "scene_order": [
            {"name": "Starting Soon"},
            {"name": "Live Race"},
            {"name": "Live Singolo"},
            {"name": "BRB"},
            {"name": "Ending"},
        ],
        "current_scene": "Starting Soon",
        "current_program_scene": "Starting Soon",
        "canvases": [],
        "current_transition": "Dissolvenza",
        "transition_duration": 300,
        "transitions": [],
        "quick_transitions": [
            {"name": "Taglio", "duration": 300, "hotkeys": [], "id": 1, "fade_to_black": False},
            {"name": "Dissolvenza", "duration": 300, "hotkeys": [], "id": 2, "fade_to_black": False},
        ],
        "saved_projectors": [],
        "preview_locked": False,
        "scaling_enabled": False,
        "scaling_level": 0,
        "scaling_off_x": 0.0,
        "scaling_off_y": 0.0,
        "modules": {
            "scripts-tool": [],
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

    out = OBS_DIR / output_filename
    out.write_text(json.dumps(collection, indent=4), encoding="utf-8")
    log.info(
        "scene collection written to %s (%d sources) in %.0f ms",
        out,
        len(collection["sources"]),
        (time.perf_counter() - t0) * 1000,
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate OBS scene collection and optional logo PNG.")
    parser.add_argument(
        "--profile",
        choices=("pigreco", "marcato"),
        default="pigreco",
        help="pigreco: PiGreco_Racing.json + logo sync; marcato: S_Marcato_42.json only",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    logo_name = "skipped"

    if args.profile == "marcato":
        log.info("start generating S.Marcato 42 OBS collection (marcato profile)")
        scene = build_collection(
            overlays=ROOT / "overlays-marcato",
            collection_name="S.Marcato 42",
            output_filename="S_Marcato_42.json",
        )
    else:
        log.info("start generating PiGreco OBS pack")
        ASSETS.mkdir(parents=True, exist_ok=True)
        logo = export_logo_png()
        logo_name = logo.name
        scene = build_collection()

    elapsed = (time.perf_counter() - started) * 1000
    log.info(
        "done in %.0f ms | logo=%s | collection=%s",
        elapsed,
        logo_name,
        scene.name,
    )


if __name__ == "__main__":
    main()
