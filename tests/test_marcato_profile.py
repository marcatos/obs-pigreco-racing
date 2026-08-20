from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from write_config_js import OUT, OVERLAYS, VALUES, write_config_js


def _parsed_config_from_js(text: str) -> dict:
    prefix = "window.PIGRECO_CONFIG = "
    start = text.index(prefix) + len(prefix)
    end = text.index(";\n\n", start)
    return json.loads(text[start:end])


def test_write_config_js_marcato_root():
    root = ROOT / "overlays-marcato"
    assert (root / "config.values.json").is_file()
    out = write_config_js(overlay_root=root)
    assert out == root / "config.js"
    text = out.read_text(encoding="utf-8")
    assert "window.PIGRECO_CONFIG" in text
    js_cfg = _parsed_config_from_js(text)
    assert js_cfg.get("sponsorsEnabled") is False
    data = json.loads((root / "config.values.json").read_text(encoding="utf-8"))
    assert data.get("sponsorsEnabled") is False
    assert "42" in str(data.get("raceNumber", "42"))
    assert "pigreco" not in data.get("teamName", "").lower()


def test_marcato_theme_matches_brand_identity():
    css = (ROOT / "overlays-marcato" / "assets" / "theme.css").read_text(encoding="utf-8")
    tokens = json.loads(
        (ROOT / "overlays-marcato" / "assets" / "brand" / "brand-tokens.json").read_text(
            encoding="utf-8"
        )
    )
    assert tokens["colors"]["carbon"].lower() == "#08080a"
    assert tokens["racing_colors"]["rosso_corsa"]["hex"].lower() == "#e10600"
    assert "abstract_system" in tokens
    assert tokens["abstract_system"]["stripe_angle_deg"] == -18.0
    assert "--carbon:" in css or "--bg:" in css
    assert "--accent:" in css or "--rosso:" in css
    assert "#08080a" in css.lower() or "#08080A" in css
    assert "#e10600" in css.lower()
    assert "--line:" in css
    assert "--panel:" in css
    assert "--font-display:" in css
    assert "--font-body:" in css
    assert "Orbitron" not in css
    assert "Space Grotesk" not in css
    assert "#00c400" not in css.lower()
    assert "#009fe5" not in css.lower()
    assert "Audiowide" in css
    assert "IBM Plex Sans" in css
    assert "weave_fine_1024_transparent.png" in css
    assert "chevron_row.svg" in css
    brand_dir = ROOT / "overlays-marcato" / "assets" / "brand"
    assert (brand_dir / "wordmark_smarcato_transparent.png").is_file()
    assert (brand_dir / "mark42_rosso_corsa_transparent.png").is_file()
    assert (brand_dir / "tag_racing_transparent.png").is_file()
    assert (brand_dir / "brand-tokens.json").is_file()
    assert (brand_dir / "abstract" / "weave_fine_1024_transparent.png").is_file()
    assert (brand_dir / "abstract" / "stripe_single_rosso_1400.png").is_file()
    # Interstitials must use ice wordmark/tag + rosso only on mark 42
    for page in ("starting-soon.html", "brb.html", "ending.html"):
        html = (ROOT / "overlays-marcato" / page).read_text(encoding="utf-8")
        assert "wordmark_smarcato_transparent.png" in html
        assert "mark42_rosso_corsa_transparent.png" in html
        assert "tag_racing_transparent.png" in html
        assert "primary_rosso_corsa_transparent.png" not in html
        assert "tag_racing_rosso_corsa" not in html
        assert "wordmark_rosso_corsa" not in html


def test_marcato_html_has_no_pigreco_assets():
    folder = ROOT / "overlays-marcato"
    for name in (
        "starting-soon.html",
        "brb.html",
        "ending.html",
        "live-chrome.html",
        "ending-cta.js",
    ):
        text = (folder / name).read_text(encoding="utf-8")
        low = text.lower()
        assert "logo-pi" not in low
        assert "logo-wordmark" not in low
        assert "sponsors.js" not in low
        assert "assets/official" not in low
        assert "qr-discord" not in low


def test_resolve_overlay_root_marcato():
    import config_server as cs

    assert cs.resolve_overlay_root({"profile": ["marcato"]}) == ROOT / "overlays-marcato"
    assert cs.resolve_overlay_root({}) == ROOT / "overlays"


def test_write_config_js_default_overlay_root():
    assert VALUES == OVERLAYS / "config.values.json"
    assert OUT == OVERLAYS / "config.js"
    out = write_config_js()
    assert out == ROOT / "overlays" / "config.js"
    assert out == OUT


def test_marcato_collection_urls():
    path = ROOT / "obs" / "S_Marcato_42.json"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "S.Marcato 42" in text or "S.Marcato" in text
    assert "overlays-marcato" in text.replace("\\\\", "/")
    assert "overlays/starting-soon.html" not in text.replace("\\\\", "/")


def test_marcato_collection_uses_dissolvenza_transition():
    path = ROOT / "obs" / "S_Marcato_42.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("current_transition") == "Dissolvenza"
    assert data.get("transition_duration") == 900
    fades = [t for t in data.get("transitions", []) if t.get("id") == "fade_transition"]
    assert len(fades) == 1
    assert fades[0]["name"] == "Dissolvenza"
    moves = [t for t in data.get("transitions", []) if t.get("id") == "move_transition"]
    assert len(moves) == 1
    assert moves[0]["name"] == "S.Marcato Move"
    settings = moves[0].get("settings") or {}
    assert settings.get("name_part_match") is True
    assert settings.get("name_number_match") is True
    assert settings.get("position_in") == (1 << 1) | (1 << 2)  # EDGE|LEFT
    assert settings.get("position_out") == (1 << 1) | (1 << 3)  # EDGE|RIGHT
    by_name = {s.get("name"): s for s in data.get("sources", []) if s.get("id") == "scene"}
    for scene_name in ("Live", "Headcam", "Ending"):
        ps = by_name[scene_name].get("private_settings") or {}
        assert ps.get("transition") == "S.Marcato Stinger"
        assert ps.get("transition_duration") == 850


def test_pigreco_collection_uses_move_transition():
    path = ROOT / "obs" / "PiGreco_Racing.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("current_transition") == "PiGreco Move"
    assert data.get("transition_duration") == 650
    moves = [t for t in data.get("transitions", []) if t.get("id") == "move_transition"]
    assert len(moves) == 1
    assert moves[0]["name"] == "PiGreco Move"


def test_marcato_replay_collection():
    path = ROOT / "obs" / "S_Marcato_Replay.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("name") == "S.Marcato Replay"
    names = {s.get("name") for s in data.get("scene_order", [])}
    # Replay pack: replay + rec only (no Live Race / Live Singolo / Live Triplo)
    assert "Live Race" not in names
    assert "Live Singolo" not in names
    assert "Live Triplo" not in names
    assert "Replay iRacing" in names
    assert "Replay Monitor" in names
    # Replay Video only if replays/race-replay.mp4 exists
    if (ROOT / "replays" / "race-replay.mp4").is_file():
        assert "Replay Video" in names
    else:
        assert "Replay Video" not in names
        assert "Race Video" not in path.read_text(encoding="utf-8")
    assert "Rec Singolo" in names
    assert "Rec Triplo" in names
    assert "Rec Singolo Live" in names
    assert "Rec Triplo Live" in names
    text = path.read_text(encoding="utf-8")
    assert "overlays-marcato" in text.replace("\\\\", "/")
    assert "replay-chrome.html" in text
    assert "live-chrome.html" not in text
    assert "pigreco_config_autostart.lua" in text.replace("\\\\", "/")
    assert "Monitor Sinistro" in text
    assert "iRacing.com Simulator:SimWinClass:iRacingSim64DX11.exe" in text
    rec_triple = next(s for s in data["sources"] if s.get("name") == "Rec Triplo")
    assert [it.get("name") for it in rec_triple.get("settings", {}).get("items", [])] == [
        "Game Capture"
    ]
    rec_triple_live = next(s for s in data["sources"] if s.get("name") == "Rec Triplo Live")
    assert [it.get("name") for it in rec_triple_live.get("settings", {}).get("items", [])] == [
        "Game Capture",
        "Overlay Triple Frame Live",
        "StreamCam",
        "Overlay Broadcast Chrome",
        "Overlay Track Map",
        "Overlay Flag FX",
    ]
    assert "broadcast-chrome.html" in text
    assert (ROOT / "overlays-marcato" / "broadcast-chrome.html").is_file()
    # Replay PIP scenes: nested Cam PIP (webcam + CAM frame) as optional block
    cam_pip = next(s for s in data["sources"] if s.get("name") == "Cam PIP")
    assert cam_pip.get("id") == "scene"
    assert [it.get("name") for it in cam_pip.get("settings", {}).get("items", [])] == [
        "Cam Backdrop Face",
        "StreamCam",
        "Overlay Cam Frame",
    ]
    assert (ROOT / "overlays-marcato" / "cam-frame.html").is_file()
    assert (ROOT / "overlays-marcato" / "cam-frame-2.html").is_file()
    cam2_pip = next(s for s in data["sources"] if s.get("name") == "Cam 2 PIP")
    assert [it.get("name") for it in cam2_pip.get("settings", {}).get("items", [])] == [
        "Cam Backdrop 2",
        "Cam 2",
        "Overlay Cam 2 Frame",
    ]
    stream = next(s for s in data["sources"] if s.get("name") == "StreamCam")
    assert stream["settings"]["resolution"] == "1280x720"
    assert stream["settings"]["frame_interval"] == 166667
    assert stream["settings"]["video_format"] == 400  # MJPEG
    assert stream["settings"].get("buffering") is False
    nv_filters = [f for f in (stream.get("filters") or []) if f.get("id") == "nv_greenscreen_filter"]
    # Greenscreen only when NVIDIA Video Effects redistributable is present on the build PC
    from generate_pack import nvidia_video_effects_installed

    if nvidia_video_effects_installed():
        assert nv_filters, "expected NVIDIA Background Removal when Video Effects SDK is installed"
        assert nv_filters[0].get("settings", {}).get("mode") == 2
        assert nv_filters[0].get("settings", {}).get("processing_interval") == 2
    else:
        assert not nv_filters, "no NVIDIA filter when Video Effects SDK is missing"
    for scene_name in ("Replay iRacing", "Replay Monitor", "Rec Singolo Live"):
        scene = next(s for s in data["sources"] if s.get("name") == scene_name)
        names = [it.get("name") for it in scene.get("settings", {}).get("items", [])]
        assert "Cam PIP" in names
        assert "Cam 2 PIP" in names
        assert "StreamCam" not in names  # cam only via Cam PIP
        assert "Overlay Broadcast Chrome" in names
    ov_bc = next(s for s in data["sources"] if s.get("name") == "Overlay Broadcast Chrome")
    assert "broadcast-chrome.html" in ov_bc.get("settings", {}).get("url", "")
    assert ov_bc["settings"]["url"].startswith("http://127.0.0.1:8766/o/marcato/")
    # Eye off by default until bridge + telemetryEnabled
    for scene_name in ("Replay iRacing", "Rec Singolo Live", "Rec Triplo Live"):
        scene = next(s for s in data["sources"] if s.get("name") == scene_name)
        bc = next(
            it
            for it in scene["settings"]["items"]
            if it.get("name") == "Overlay Broadcast Chrome"
        )
        assert bc.get("visible") is False
    ov_replay = next(s for s in data["sources"] if s.get("name") == "Overlay Replay Chrome")
    assert "cam=0" in ov_replay.get("settings", {}).get("url", "")
    ov = next(s for s in data["sources"] if s.get("name") == "Overlay Triple Frame Live")
    assert "badge=REPLAY" in ov.get("settings", {}).get("url", "")
    assert (ROOT / "overlays-marcato" / "triple-frame.html").is_file()
    assert (ROOT / "overlays-marcato" / "replay-chrome.html").is_file()
    assert (ROOT / "replays" / "LEGGIMI.txt").is_file()


def test_marcato_live_headcam_and_pedals():
    """Slim live: Game Capture + face/pedals; Headcam = Brio + pedals; no USB Camera."""
    path = ROOT / "obs" / "S_Marcato_42.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    names = {s.get("name") for s in data.get("scene_order", [])}
    assert names == {
        "Starting Soon",
        "Live",
        "Headcam",
        "Lobby",
        "BRB",
        "Ending",
    }
    assert "Live Race" not in names
    assert "Rec Singolo" not in names

    source_names = {s.get("name") for s in data["sources"]}
    assert "Game Capture" in source_names
    assert "Cam Head" in source_names
    assert "Cam Pedals" in source_names
    assert "Cam Pedals PIP" in source_names
    assert "Cam PIP" in source_names
    assert "USB Camera" not in path.read_text(encoding="utf-8")
    assert "Cam 2" not in source_names
    assert "Monitor Centro" not in source_names

    ui = next(s for s in data["sources"] if s.get("name") == "iRacing UI Capture")
    assert ui["id"] == "window_capture"
    assert ui["settings"].get("method") == 2
    assert "iRacingUI.exe" in ui["settings"].get("window", "")

    lobby = next(s for s in data["sources"] if s.get("name") == "Lobby")
    lobby_items = [it.get("name") for it in lobby["settings"]["items"]]
    assert lobby_items[0] == "iRacing UI Capture"

    live = next(s for s in data["sources"] if s.get("name") == "Live")
    live_items = [it.get("name") for it in live["settings"]["items"]]
    assert live_items[0] == "Game Capture"
    assert "Cam PIP" in live_items
    assert "Cam Pedals PIP" in live_items
    assert "Microfono" in live_items
    pedals_live = next(it for it in live["settings"]["items"] if it["name"] == "Cam Pedals PIP")
    assert pedals_live.get("visible") is True

    head = next(s for s in data["sources"] if s.get("name") == "Headcam")
    head_items = [it.get("name") for it in head["settings"]["items"]]
    assert head_items == [
        "Cam Head",
        "Overlay Live Chrome",
        "Overlay Broadcast Chrome",
        "Overlay Track Map",
        "Cam Pedals PIP",
        "Microfono",
    ]
    assert "Game Capture" not in head_items
    bc_head = next(
        it for it in head["settings"]["items"] if it["name"] == "Overlay Broadcast Chrome"
    )
    assert bc_head.get("visible") is True
    tm_head = next(it for it in head["settings"]["items"] if it["name"] == "Overlay Track Map")
    assert tm_head.get("visible") is False

    cam_head = next(s for s in data["sources"] if s.get("name") == "Cam Head")
    assert "vid_046d" in cam_head["settings"]["video_device_id"].lower()
    assert "pid_085e" in cam_head["settings"]["video_device_id"].lower()
    assert not (cam_head.get("filters") or [])

    cam_pedals = next(s for s in data["sources"] if s.get("name") == "Cam Pedals")
    assert "vid_041e" in cam_pedals["settings"]["video_device_id"].lower()
    assert not (cam_pedals.get("filters") or [])

    pedals_pip = next(s for s in data["sources"] if s.get("name") == "Cam Pedals PIP")
    assert [it.get("name") for it in pedals_pip["settings"]["items"]] == [
        "Cam Backdrop Pedals",
        "Cam Pedals",
        "Overlay Cam Pedals Frame",
    ]
    pedals_item = next(it for it in pedals_pip["settings"]["items"] if it["name"] == "Cam Pedals")
    assert pedals_item["crop_left"] == 360
    assert pedals_item["crop_top"] == 220
    assert pedals_item["crop_right"] == 360
    assert pedals_item["crop_bottom"] == 185
    # Zoomed scale fills 320px PiP from cropped 1200px source width
    assert abs(pedals_item["scale"]["x"] - (320.0 / 1200.0)) < 1e-6


def test_marcato_rec_2k_collection():
    path = ROOT / "obs" / "S_Marcato_Rec_2K.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("name") == "S.Marcato Rec 2K"
    assert data.get("resolution") == {"x": 2560, "y": 1440}
    names = {s.get("name") for s in data.get("scene_order", [])}
    assert names == {
        "Rec Singolo",
        "Rec Triplo",
        "Rec Singolo Live",
        "Rec Triplo Live",
        "Flag Yellow",
        "Flag Red",
        "Flag Checkered",
    }
    assert "Live Race" not in names
    rec_single = next(s for s in data["sources"] if s.get("name") == "Rec Singolo")
    items = rec_single["settings"]["items"]
    assert [it["name"] for it in items] == ["Monitor Centrale", "Game Capture"]
    assert items[0].get("visible") is False
    assert items[1].get("visible") is True

    live = next(s for s in data["sources"] if s.get("name") == "Rec Singolo Live")
    live_names = [it.get("name") for it in live["settings"]["items"]]
    assert live_names == [
        "Monitor Centrale",
        "Game Capture",
        "Overlay Live Chrome",
        "Overlay Broadcast Chrome",
        "Overlay Track Map",
        "Cam PIP",
        "Cam 2 PIP",
        "Overlay Flag FX",
    ]
    assert live["settings"]["items"][0].get("visible") is False
    assert live["settings"]["items"][1].get("visible") is True
    ov_item = next(it for it in live["settings"]["items"] if it["name"] == "Overlay Live Chrome")
    # 1920 overlay scaled 4/3 onto 2560 canvas
    assert abs(ov_item["scale"]["x"] - (2560 / 1920)) < 1e-9
    bc = next(
        it for it in live["settings"]["items"] if it["name"] == "Overlay Broadcast Chrome"
    )
    assert bc.get("visible") is False
    assert abs(bc["scale"]["x"] - (2560 / 1920)) < 1e-9

    triple_live = next(s for s in data["sources"] if s.get("name") == "Rec Triplo Live")
    assert [it.get("name") for it in triple_live["settings"]["items"]] == [
        "Game Capture",
        "Overlay Triple Frame Live",
        "Overlay Broadcast Chrome",
        "Overlay Track Map",
        "StreamCam",
        "Cam 2 PIP",
        "Overlay Flag FX",
    ]
    text = path.read_text(encoding="utf-8")
    assert "overlays-marcato" in text.replace("\\\\", "/")
    assert "live-chrome.html" in text
    assert "broadcast-chrome.html" in text
    assert "triple-frame.html" in text

    profile = ROOT / "obs" / "profiles" / "Rec_2K" / "basic.ini"
    assert profile.is_file()
    ini = profile.read_text(encoding="utf-8")
    assert "BaseCX=2560" in ini
    assert "BaseCY=1440" in ini
    assert "RecEncoder=obs_nvenc_hevc_tex" in ini
    assert "RecSplitFile=true" in ini
    assert "RefreshToken=" not in ini
    assert "Token=" not in ini

    encoder = json.loads(
        (ROOT / "obs" / "profiles" / "Rec_2K" / "recordEncoder.json").read_text(
            encoding="utf-8"
        )
    )
    assert encoder.get("rate_control") == "VBR"
    assert encoder.get("bitrate") == 25000
    assert encoder.get("max_bitrate") == 40000
    assert encoder.get("profile") == "main"


def test_rec_triplo_game_bounds_and_cam_slot():
    """OBS relative bounds use size_from_absolute (2*px/canvas_h), not /canvas_w."""
    sys.path.insert(0, str(ROOT / "tools"))
    import generate_pack as gp

    band_h = gp._TRIPLE_SAFE_H
    brel = gp.size_rel((1920.0, band_h))
    assert abs(brel["x"] - (2.0 * 1920.0 / 1080.0)) < 1e-9
    assert abs(brel["y"] - (2.0 * band_h / 1080.0)) < 1e-9
    cam_x, cam_y = gp.triple_cam_pos()
    assert abs(cam_x - 1480.0) < 1e-6
    assert abs(cam_y - 840.0) < 1e-6

    for coll in ("S_Marcato_Replay.json",):
        data = json.loads((ROOT / "obs" / coll).read_text(encoding="utf-8"))
        scene = next(s for s in data["sources"] if s.get("name") == "Rec Triplo Live")
        items = {it["name"]: it for it in scene["settings"]["items"]}
        game = items["Game Capture"]
        assert game["bounds_type"] == 3  # Scale Outer (zoom/crop)
        assert game["bounds_crop"] is True
        assert abs(game["bounds"]["x"] - 1920.0) < 1e-6
        assert abs(game["bounds"]["y"] - band_h) < 1e-6
        assert abs(game["bounds_rel"]["x"] - brel["x"]) < 1e-9
        assert abs(game["bounds_rel"]["y"] - brel["y"]) < 1e-9
        assert abs(game["pos"]["y"] - gp.triple_band_h()) < 1e-6
        cam = items["StreamCam"]
        assert abs(cam["pos"]["x"] - cam_x) < 1e-6
        assert abs(cam["pos"]["y"] - cam_y) < 1e-6
