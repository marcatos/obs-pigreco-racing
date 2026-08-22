"""PiGreco OBS pack — OBS integration (dock, services, install state)."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("pigreco_install")

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path.home() / "AppData" / "Local" / "PiGrecoOBS"
STATE_FILE = STATE_DIR / "install.json"
OBS_APPDATA = Path.home() / "AppData" / "Roaming" / "obs-studio"
OBS_SCENES = OBS_APPDATA / "basic" / "scenes"

DOCK_TITLE = "PiGreco Config"
DOCK_URL = "http://127.0.0.1:8766/"
DOCK_UUID = "pigrecoconfigdock01"

PRESERVE_ON_SYNC = {
    "overlays/config.values.json",
    "overlays/config.js",
    "overlays-marcato/config.values.json",
    "overlays-marcato/config.js",
    "adapters/obs_flag_director/config.local.json",
}

SCENE_FILES = (
    "PiGreco_Racing.json",
    "S_Marcato_42.json",
    "S_Marcato_Replay.json",
    "S_Marcato_Rec_2K.json",
)


def _norm_rel(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def read_state() -> dict | None:
    if not STATE_FILE.is_file():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("state read failed: %s", exc)
        return None


def write_state(*, pack_root: Path, profiles: list[str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "pack_root": str(pack_root.resolve()),
        "profiles": profiles,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log.info("state written %s", STATE_FILE)


def clear_state() -> None:
    if STATE_FILE.is_file():
        STATE_FILE.unlink()
        log.info("state removed %s", STATE_FILE)


def merge_browser_docks(existing_raw: str) -> str:
    docks: list[dict[str, str]] = []
    if existing_raw and existing_raw.strip():
        try:
            parsed = json.loads(existing_raw)
            if isinstance(parsed, list):
                docks = [d for d in parsed if isinstance(d, dict)]
        except json.JSONDecodeError:
            log.warning("invalid ExtraBrowserDocks JSON, replacing")
    docks = [
        d
        for d in docks
        if d.get("title") != DOCK_TITLE and DOCK_URL not in str(d.get("url", ""))
    ]
    docks.append({"title": DOCK_TITLE, "url": DOCK_URL, "uuid": DOCK_UUID})
    return json.dumps(docks, ensure_ascii=True)


def _set_ini_key(ini_path: Path, key: str, value: str) -> bool:
    if not ini_path.is_file():
        return False
    text = ini_path.read_text(encoding="utf-8", errors="replace")
    section = "[BasicWindow]"
    if section not in text:
        text = text.rstrip() + f"\n\n{section}\n"
    pattern = rf"(?m)^({re.escape(key)}=).*$"
    if re.search(pattern, text):
        text = re.sub(pattern, rf"\1{value}", text, count=1)
    else:
        if section in text:
            text = text.replace(section, f"{section}\n{key}={value}", 1)
        else:
            text += f"\n{section}\n{key}={value}\n"
    ini_path.write_text(text, encoding="utf-8")
    log.info("updated %s key=%s", ini_path.name, key)
    return True


def ensure_browser_dock() -> None:
    payload = merge_browser_docks("")
    updated = False
    for name in ("user.ini", "global.ini"):
        path = OBS_APPDATA / name
        if not path.is_file():
            continue
        raw = ""
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("ExtraBrowserDocks="):
                raw = line.split("=", 1)[1]
                break
        merged = merge_browser_docks(raw)
        if _set_ini_key(path, "ExtraBrowserDocks", merged):
            updated = True
    if not updated:
        user_ini = OBS_APPDATA / "user.ini"
        user_ini.parent.mkdir(parents=True, exist_ok=True)
        if not user_ini.is_file():
            user_ini.write_text(f"[BasicWindow]\nExtraBrowserDocks={payload}\n", encoding="utf-8")
        else:
            _set_ini_key(user_ini, "ExtraBrowserDocks", payload)
        log.info("created browser dock in user.ini")


def remove_browser_dock() -> None:
    for name in ("user.ini", "global.ini"):
        path = OBS_APPDATA / name
        if not path.is_file():
            continue
        raw = ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines:
            if line.startswith("ExtraBrowserDocks="):
                raw = line.split("=", 1)[1]
                break
        if not raw:
            continue
        try:
            docks = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(docks, list):
            continue
        filtered = [
            d
            for d in docks
            if isinstance(d, dict)
            and d.get("title") != DOCK_TITLE
            and DOCK_URL not in str(d.get("url", ""))
        ]
        _set_ini_key(path, "ExtraBrowserDocks", json.dumps(filtered, ensure_ascii=True))


def ensure_director_config() -> None:
    example = ROOT / "adapters" / "obs_flag_director" / "config.example.json"
    local = ROOT / "adapters" / "obs_flag_director" / "config.local.json"
    if local.is_file():
        log.info("director config exists %s", local)
        return
    if not example.is_file():
        log.warning("missing %s", example)
        return
    shutil.copy2(example, local)
    log.info("created director config from example -> %s", local)


def _run_vbs(vbs: Path) -> int:
    if not vbs.is_file():
        log.warning("missing %s", vbs)
        return 0
    wscript = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe"
    if not wscript.is_file():
        wscript = Path("wscript.exe")
    proc = subprocess.run(
        [str(wscript), "//nologo", str(vbs)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        log.warning("vbs exit=%s stderr=%s", proc.returncode, (proc.stderr or "").strip())
    else:
        log.info("started via %s", vbs.name)
    return proc.returncode


def start_background_services() -> None:
    t0 = time.perf_counter()
    _run_vbs(ROOT / "tools" / "ensure_config_server_silent.vbs")
    _run_vbs(ROOT / "tools" / "ensure_session_director_silent.vbs")
    log.info("background services triggered in %.0f ms", (time.perf_counter() - t0) * 1000)


def install_startup_shortcut() -> None:
    ps1 = ROOT / "tools" / "install_config_autostart.ps1"
    if not ps1.is_file():
        return
    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
        ],
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        log.warning("install_config_autostart exit=%s", proc.returncode)
    else:
        log.info("config autostart shortcut installed")


def remove_startup_shortcut() -> None:
    ps1 = ROOT / "tools" / "install_config_autostart.ps1"
    if not ps1.is_file():
        return
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            "-Remove",
        ],
        cwd=str(ROOT),
    )


def remove_scene_collections() -> None:
    if not OBS_SCENES.is_dir():
        return
    for name in SCENE_FILES:
        path = OBS_SCENES / name
        if path.is_file():
            path.unlink()
            log.info("removed scene collection %s", path)


def sync_pack_from_staging(staging: Path, dest: Path) -> None:
    if not staging.is_dir():
        raise FileNotFoundError(staging)
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0
    for src in staging.rglob("*"):
        if src.is_dir():
            continue
        rel = _norm_rel(src, staging)
        if rel in PRESERVE_ON_SYNC and (dest / rel).is_file():
            skipped += 1
            continue
        if rel.startswith("logs/"):
            skipped += 1
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
        copied += 1
    log.info("sync pack copied=%d skipped=%d dest=%s", copied, skipped, dest)


def cmd_install(args: argparse.Namespace) -> int:
    pack_root = Path(args.pack_root).resolve()
    profiles = [p.strip().lower() for p in args.profiles.split(",") if p.strip()]
    log.info("install pack_root=%s profiles=%s", pack_root, profiles)
    ensure_director_config()
    ensure_browser_dock()
    install_startup_shortcut()
    start_background_services()
    write_state(pack_root=pack_root, profiles=profiles or ["pigreco"])
    log.info("install complete")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    log.info("uninstall start")
    remove_browser_dock()
    remove_startup_shortcut()
    remove_scene_collections()
    clear_state()
    if args.remove_pack_dir:
        pack = Path(args.pack_root).resolve()
        if pack.is_dir():
            shutil.rmtree(pack)
            log.info("removed pack dir %s", pack)
    log.info("uninstall complete")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    sync_pack_from_staging(Path(args.staging), Path(args.dest))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PiGreco OBS integration installer")
    p.add_argument("--log-level", default="INFO")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser("install", help="Register dock, autostart, services")
    p_install.add_argument("--pack-root", default=str(ROOT))
    p_install.add_argument("--profiles", default="pigreco")
    p_install.set_defaults(func=cmd_install)

    p_un = sub.add_parser("uninstall", help="Remove dock, shortcuts, scene JSON")
    p_un.add_argument("--pack-root", default=str(ROOT))
    p_un.add_argument("--remove-pack-dir", action="store_true")
    p_un.set_defaults(func=cmd_uninstall)

    p_sync = sub.add_parser("sync", help="Sync staging tree into installed pack")
    p_sync.add_argument("staging")
    p_sync.add_argument("dest")
    p_sync.set_defaults(func=cmd_sync)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    started = time.perf_counter()
    try:
        rc = args.func(args)
        log.info("done exit=%s total_ms=%.0f", rc, (time.perf_counter() - started) * 1000)
        return rc
    except Exception:
        log.exception("failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
