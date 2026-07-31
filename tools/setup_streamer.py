"""Personalize the pack for a streamer (username + local OBS paths)."""
from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("setup_streamer")

ROOT = Path(__file__).resolve().parents[1]
OVERLAYS = ROOT / "overlays"
CONFIG_JS = OVERLAYS / "config.js"
EXAMPLE = OVERLAYS / "config.example.js"
OBS_JSON = ROOT / "obs" / "PiGreco_Racing.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Parametrize PiGreco OBS pack for a streamer (username, paths)."
    )
    p.add_argument("--username", required=True, help="Twitch/username nick (senza @)")
    p.add_argument("--pilot-name", default="", help="Nome visualizzato (default=username)")
    p.add_argument("--team-name", default="PiGreco Racing")
    p.add_argument("--event-title", default="Sim Racing Session")
    p.add_argument(
        "--install-obs",
        action="store_true",
        help="Copia la collezione in %%APPDATA%%/obs-studio/basic/scenes/",
    )
    p.add_argument(
        "--regen-collection",
        action="store_true",
        default=True,
        help="Rigenera obs/PiGreco_Racing.json con path locali (default: on)",
    )
    return p.parse_args()


def write_config(username: str, pilot_name: str, team_name: str, event_title: str) -> None:
    nick = username.lstrip("@").strip()
    pilot = pilot_name.strip() or nick
    handle = "@" + nick
    if not CONFIG_JS.exists() and EXAMPLE.exists():
        shutil.copy2(EXAMPLE, CONFIG_JS)
        log.info("created config.js from example")

    text = CONFIG_JS.read_text(encoding="utf-8")

    def repl_str(key: str, value: str, src: str) -> str:
        pattern = rf'({key}\s*:\s*)"(.*?)"'
        if re.search(pattern, src):
            return re.sub(pattern, rf'\1"{value}"', src, count=1)
        return src

    for key, value in [
        ("username", nick),
        ("pilotName", pilot),
        ("twitchHandle", handle),
        ("teamName", team_name),
        ("eventTitle", event_title),
    ]:
        text = repl_str(key, value, text)

    CONFIG_JS.write_text(text, encoding="utf-8")
    log.info("updated %s (username=%s, pilot=%s)", CONFIG_JS.name, nick, pilot)


def regen_and_maybe_install(install: bool) -> None:
    t0 = time.perf_counter()
    gen = ROOT / "tools" / "generate_pack.py"
    import runpy

    runpy.run_path(str(gen), run_name="__main__")
    log.info("regenerated collection in %.0f ms", (time.perf_counter() - t0) * 1000)

    # Patch browser URLs are already absolute via generate_pack file_url(ROOT)
    if install:
        dest_dir = Path.home() / "AppData/Roaming/obs-studio/basic/scenes"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "PiGreco_Racing.json"
        shutil.copy2(OBS_JSON, dest)
        log.info("installed scene collection -> %s", dest)


def main() -> None:
    started = time.perf_counter()
    args = parse_args()
    log.info("start setup_streamer username=%s", args.username)
    write_config(args.username, args.pilot_name, args.team_name, args.event_title)
    if args.regen_collection:
        regen_and_maybe_install(args.install_obs)
    elif args.install_obs:
        dest = Path.home() / "AppData/Roaming/obs-studio/basic/scenes/PiGreco_Racing.json"
        shutil.copy2(OBS_JSON, dest)
        log.info("installed existing collection -> %s", dest)

    # Verify config JSON-ish keys present
    cfg_txt = CONFIG_JS.read_text(encoding="utf-8")
    if "username" not in cfg_txt:
        raise SystemExit("config.js missing username after write")

    log.info(
        "done in %.0f ms | share folder: %s | teammates: copy pack, run setup_streamer.py --username THEIR_NICK --install-obs",
        (time.perf_counter() - started) * 1000,
        ROOT,
    )


if __name__ == "__main__":
    main()
