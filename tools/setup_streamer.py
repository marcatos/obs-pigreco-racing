"""Personalize the pack for a streamer (username + local OBS paths)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("setup_streamer")

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
OVERLAYS = ROOT / "overlays"
CONFIG_JS = OVERLAYS / "config.js"
CONFIG_VALUES = OVERLAYS / "config.values.json"
OBS_JSON = ROOT / "obs" / "PiGreco_Racing.json"

VALID_PROFILES = ("pigreco", "marcato")
DEFAULT_PROFILES = ("pigreco",)


def parse_profiles(raw: str) -> tuple[str, ...]:
    """Normalize --profiles (comma/space separated). Default: pigreco only."""
    if not raw or not raw.strip():
        return DEFAULT_PROFILES
    names: list[str] = []
    for part in raw.replace(",", " ").split():
        name = part.strip().lower()
        if not name:
            continue
        if name not in VALID_PROFILES:
            raise SystemExit(f"Profilo sconosciuto: {name!r} (validi: {', '.join(VALID_PROFILES)})")
        if name not in names:
            names.append(name)
    return tuple(names or DEFAULT_PROFILES)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Parametrize PiGreco OBS pack for a streamer (username, paths)."
    )
    p.add_argument("--username", required=True, help="Twitch/username nick (senza @)")
    p.add_argument("--pilot-name", default="", help="Nome visualizzato (default=username)")
    p.add_argument("--team-name", default="PiGreco Racing")
    p.add_argument("--event-title", default="Sim Racing Session")
    p.add_argument(
        "--profiles",
        default="pigreco",
        help="Pack OBS da generare/installare: pigreco, marcato (separati da virgola). Default: pigreco",
    )
    p.add_argument(
        "--install-obs",
        action="store_true",
        help="Copia le collezioni selezionate in %%APPDATA%%/obs-studio/basic/scenes/",
    )
    p.add_argument(
        "--regen-collection",
        action="store_true",
        default=True,
        help="Rigenera i JSON scene con path locali (default: on)",
    )
    return p.parse_args()


def write_config(username: str, pilot_name: str, team_name: str, event_title: str) -> None:
    nick = username.lstrip("@").strip()
    pilot = pilot_name.strip() or nick
    handle = "@" + nick

    if not CONFIG_VALUES.exists():
        raise SystemExit(f"Missing {CONFIG_VALUES}")

    values = json.loads(CONFIG_VALUES.read_text(encoding="utf-8"))
    values["username"] = nick
    values["pilotName"] = pilot
    values["twitchHandle"] = handle
    values["teamName"] = team_name
    values["eventTitle"] = event_title

    from write_config_js import write_config_js

    write_config_js(values)
    log.info("updated config.values.json + config.js (username=%s, pilot=%s)", nick, pilot)


def _load_generate_pack():
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    import generate_pack  # noqa: E402

    return generate_pack


def regenerate_profiles(profiles: tuple[str, ...]) -> dict[str, list[Path]]:
    pack = _load_generate_pack()
    generated: dict[str, list[Path]] = {}
    t0 = time.perf_counter()

    if "pigreco" in profiles:
        pack.ASSETS.mkdir(parents=True, exist_ok=True)
        pack.export_logo_png()
        scene = pack.build_collection(profile="pigreco")
        generated["pigreco"] = [scene]
        log.info("generated PiGreco collection -> %s", scene)

    if "marcato" in profiles:
        overlays = ROOT / "overlays-marcato"
        paths = [
            pack.build_marcato_live_collection(overlays=overlays),
            pack.build_replay_collection(overlays=overlays),
            pack.build_rec_2k_collection(overlays=overlays),
        ]
        pack.install_rec_2k_profile()
        generated["marcato"] = paths
        log.info(
            "generated Marcato collections -> %s",
            ", ".join(p.name for p in paths),
        )

    log.info(
        "regenerated profiles=%s in %.0f ms",
        ",".join(profiles),
        (time.perf_counter() - t0) * 1000,
    )
    return generated


def install_profiles_to_obs(profiles: tuple[str, ...], generated: dict[str, list[Path]]) -> None:
    pack = _load_generate_pack()
    t0 = time.perf_counter()
    pack.stop_obs()

    if "marcato" in profiles:
        for src in generated.get("marcato", []):
            activate = profiles == ("marcato",) and src.name == "S_Marcato_42.json"
            pack.install_obs_scene_collection(src, activate=activate)

    if "pigreco" in profiles:
        pigreco = generated.get("pigreco", [])
        if not pigreco:
            raise SystemExit("PiGreco collection missing after regenerate")
        pack.install_obs_scene_collection(pigreco[0], activate=True)

    pack.start_obs()
    log.info(
        "installed profiles=%s to OBS in %.0f ms",
        ",".join(profiles),
        (time.perf_counter() - t0) * 1000,
    )


def regen_and_maybe_install(profiles: tuple[str, ...], install: bool) -> None:
    generated = regenerate_profiles(profiles)
    if install:
        install_profiles_to_obs(profiles, generated)


def main() -> None:
    started = time.perf_counter()
    args = parse_args()
    profiles = parse_profiles(args.profiles)
    log.info("start setup_streamer username=%s profiles=%s", args.username, ",".join(profiles))

    if "pigreco" in profiles:
        write_config(args.username, args.pilot_name, args.team_name, args.event_title)
    else:
        log.info("skip PiGreco config write (profiles=%s)", ",".join(profiles))

    if args.regen_collection:
        regen_and_maybe_install(profiles, args.install_obs)
    elif args.install_obs:
        pack = _load_generate_pack()
        generated: dict[str, list[Path]] = {}
        if "pigreco" in profiles and OBS_JSON.is_file():
            generated["pigreco"] = [OBS_JSON]
        for name in ("S_Marcato_42.json", "S_Marcato_Replay.json", "S_Marcato_Rec_2K.json"):
            path = ROOT / "obs" / name
            if "marcato" in profiles and path.is_file():
                generated.setdefault("marcato", []).append(path)
        if not generated:
            raise SystemExit("Nessuna collezione da installare; usa --regen-collection o rigenera prima.")
        install_profiles_to_obs(profiles, generated)

    if "pigreco" in profiles:
        cfg_txt = CONFIG_JS.read_text(encoding="utf-8")
        if "username" not in cfg_txt:
            raise SystemExit("config.js missing username after write")

    log.info(
        "done in %.0f ms | profiles=%s | share folder: %s",
        (time.perf_counter() - started) * 1000,
        ",".join(profiles),
        ROOT,
    )


if __name__ == "__main__":
    main()
