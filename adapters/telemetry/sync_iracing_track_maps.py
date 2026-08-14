"""
Sync iRacing track outlines into a local gitignored cache.

Sources:
  paths-dump (default) — official activePath geometry from a public track_info dump
                         (no login; works while iRacing OAuth client registration is paused)
  api — members-ng /data/track/assets (needs OAuth client_id + secret + user creds)

Credentials for api (never logged):
  adapters/telemetry/iracing_api.local.json
  { "email", "password", "client_id", "client_secret" }

Usage:
  python adapters/telemetry/sync_iracing_track_maps.py
  python adapters/telemetry/sync_iracing_track_maps.py --track-id 449
  python adapters/telemetry/sync_iracing_track_maps.py --source api --force
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from domain_track_map import path_viewbox

log = logging.getLogger("pigreco.telemetry.sync_track_maps")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "overlays" / "assets" / "tracks" / "iracing"
ASSETS_URL = "https://members-ng.iracing.com/data/track/assets"
LOCAL_CREDS = Path(__file__).resolve().parent / "iracing_api.local.json"
# Community dump of iRacing activePath layers (TrackID → path d=)
PATHS_DUMP_URL = (
    "https://raw.githubusercontent.com/xikxp1/iRaceHUD/main/"
    "static/track_info_data/track_info.json"
)
SETTINGS_DUMP_URL = (
    "https://raw.githubusercontent.com/xikxp1/iRaceHUD/main/"
    "static/track_info_data/track_settings.json"
)
PREFERRED_LAYERS = ("active", "track", "default", "background")
UA = "obs-pigreco-racing-track-sync/1.2"


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def svg_from_active_path(d: str) -> str:
    vb = path_viewbox(d, pad=100.0)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" overflow="visible">\n'
        f'  <path fill="none" stroke="#0a0a0a" stroke-width="20" '
        f'stroke-linecap="round" stroke-linejoin="round" d="{d}"/>\n'
        "</svg>\n"
    )


def write_meta(
    path: Path,
    *,
    layer: str,
    force: bool,
    offset: float = 0.0,
    direction: int = 1,
) -> None:
    if path.is_file() and not force:
        return
    path.write_text(
        json.dumps(
            {
                "offset": float(offset),
                "direction": -1 if int(direction) < 0 else 1,
                "layer": layer,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _http_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sync_from_paths_dump(
    *,
    out_dir: Path,
    track_ids: set[str] | None,
    force: bool,
    dump_url: str,
    settings_url: str = SETTINGS_DUMP_URL,
) -> dict[str, int]:
    t0 = time.perf_counter()
    log.info("Downloading track path dump (no auth) url=%s", dump_url.split("?")[0])
    catalog = _http_json(dump_url)
    if not isinstance(catalog, dict):
        raise RuntimeError("Unexpected track_info dump shape")

    settings: dict[str, Any] = {}
    try:
        log.info("Downloading track settings (offset/direction) url=%s", settings_url.split("?")[0])
        raw_settings = _http_json(settings_url)
        if isinstance(raw_settings, dict):
            settings = raw_settings
            log.info("Loaded settings for %d tracks", len(settings))
    except Exception as exc:  # noqa: BLE001
        log.warning("track_settings download failed (%s) — using offset=0 direction=1", exc)

    out_dir.mkdir(parents=True, exist_ok=True)
    keys = sorted(catalog.keys(), key=lambda k: int(k) if str(k).isdigit() else 0)
    if track_ids:
        keys = [k for k in keys if str(k) in track_ids]
        missing = track_ids - set(map(str, keys))
        if missing:
            log.warning("Track IDs not in dump: %s", ", ".join(sorted(missing)))

    stats = {"ok": 0, "skip": 0, "fail": 0, "total": len(keys)}
    for i, tid in enumerate(keys, start=1):
        entry = catalog.get(tid) or {}
        cfg = settings.get(str(tid)) if isinstance(settings.get(str(tid)), dict) else {}
        d = ""
        layer = "activePath"
        if isinstance(cfg, dict) and str(cfg.get("customTrackPath") or "").strip():
            d = str(cfg.get("customTrackPath")).strip()
            layer = "customTrackPath"
        elif isinstance(entry, dict):
            d = str(entry.get("activePath") or entry.get("path") or "").strip()
        offset = float(cfg.get("offset") or 0.0) if isinstance(cfg, dict) else 0.0
        direction = int(cfg.get("direction") or 1) if isinstance(cfg, dict) else 1

        svg_path = out_dir / f"{tid}.svg"
        meta_path = out_dir / f"{tid}.meta.json"
        if not d:
            stats["fail"] += 1
            continue
        if svg_path.is_file() and not force:
            stats["skip"] += 1
            write_meta(
                meta_path,
                layer=layer,
                force=True,  # always refresh calibration
                offset=offset,
                direction=direction,
            )
        else:
            try:
                svg_path.write_text(svg_from_active_path(d), encoding="utf-8")
                write_meta(
                    meta_path,
                    layer=layer,
                    force=True,
                    offset=offset,
                    direction=direction,
                )
                stats["ok"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["fail"] += 1
                log.error("[%d/%d] trackId=%s failed: %s", i, stats["total"], tid, exc)
                continue
        if i == 1 or i % 50 == 0 or i == stats["total"]:
            pct = 100.0 * i / max(1, stats["total"])
            log.info(
                "Progress %d/%d (%.0f%%) ok=%d skip=%d fail=%d",
                i,
                stats["total"],
                pct,
                stats["ok"],
                stats["skip"],
                stats["fail"],
            )

    elapsed = time.perf_counter() - t0
    log.info(
        "Paths-dump sync done in %.1fs — total=%d ok=%d skip=%d fail=%d out=%s",
        elapsed,
        stats["total"],
        stats["ok"],
        stats["skip"],
        stats["fail"],
        out_dir,
    )
    return stats


def pick_layer(layers: dict[str, str]) -> tuple[str, str] | None:
    if not layers:
        return None
    lower_map = {str(k).lower(): (str(k), str(v)) for k, v in layers.items()}
    for pref in PREFERRED_LAYERS:
        if pref in lower_map:
            return lower_map[pref]
    first_key = next(iter(layers))
    return str(first_key), str(layers[first_key])


def resolve_svg_url(track_map_base: str, layer_rel: str) -> str:
    from urllib.parse import urljoin

    base = track_map_base if track_map_base.endswith("/") else track_map_base + "/"
    return urljoin(base, layer_rel.lstrip("/"))


def sync_from_api(
    *,
    out_dir: Path,
    track_ids: set[str] | None,
    force: bool,
) -> dict[str, int]:
    from iracing_members_auth import fetch_bytes, fetch_json, login_oauth_or_legacy

    t0 = time.perf_counter()
    opener = login_oauth_or_legacy(LOCAL_CREDS)
    log.info("Fetching track assets catalog via Data API")
    catalog = fetch_json(opener, ASSETS_URL)
    if not isinstance(catalog, dict):
        raise RuntimeError("Unexpected track/assets payload type")

    out_dir.mkdir(parents=True, exist_ok=True)
    keys = sorted(catalog.keys(), key=lambda k: int(k) if str(k).isdigit() else 0)
    if track_ids:
        keys = [k for k in keys if str(k) in track_ids]
        missing = track_ids - set(map(str, keys))
        if missing:
            log.warning("Track IDs not in catalog: %s", ", ".join(sorted(missing)))

    stats = {"ok": 0, "skip": 0, "fail": 0, "total": len(keys)}
    for i, tid in enumerate(keys, start=1):
        asset = catalog.get(tid)
        if not isinstance(asset, dict):
            stats["fail"] += 1
            continue
        svg_path = out_dir / f"{tid}.svg"
        meta_path = out_dir / f"{tid}.meta.json"
        if svg_path.is_file() and not force:
            stats["skip"] += 1
            write_meta(meta_path, layer="api", force=False)
            continue
        layers = asset.get("track_map_layers") or {}
        if not isinstance(layers, dict):
            layers = {}
        picked = pick_layer(layers)
        track_map = str(asset.get("track_map") or "")
        if not picked or not track_map:
            stats["fail"] += 1
            log.warning("[%d/%d] trackId=%s missing track_map / layers", i, stats["total"], tid)
            continue
        _key, rel = picked
        url = resolve_svg_url(track_map, rel)
        try:
            svg = fetch_bytes(opener, url)
            text = svg.decode("utf-8", errors="replace")
            if "<svg" not in text.lower():
                raise RuntimeError("response is not SVG")
            svg_path.write_text(text, encoding="utf-8")
            write_meta(meta_path, layer=rel, force=True)
            stats["ok"] += 1
            log.info("[%d/%d] wrote %s (%d bytes)", i, stats["total"], svg_path.name, len(text))
        except Exception as exc:  # noqa: BLE001
            stats["fail"] += 1
            log.error("[%d/%d] trackId=%s failed: %s", i, stats["total"], tid, exc)

    elapsed = time.perf_counter() - t0
    log.info(
        "API sync done in %.1fs — total=%d ok=%d skip=%d fail=%d out=%s",
        elapsed,
        stats["total"],
        stats["ok"],
        stats["skip"],
        stats["fail"],
        out_dir,
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sync iRacing track map SVGs to local cache")
    p.add_argument("--track-id", action="append", dest="track_ids", help="Filter TrackID (repeatable)")
    p.add_argument("--force", action="store_true", help="Re-download even if SVG exists")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory")
    p.add_argument(
        "--source",
        choices=("paths-dump", "api"),
        default="paths-dump",
        help="paths-dump=no login (default); api=OAuth Data API",
    )
    p.add_argument("--dump-url", default=PATHS_DUMP_URL, help="URL for paths-dump JSON")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)
    _setup_logging(args.log_level)
    ids = {str(x).strip() for x in (args.track_ids or []) if str(x).strip()} or None
    log.info(
        "Starting track map sync source=%s out=%s force=%s filter=%s",
        args.source,
        args.out,
        args.force,
        ids,
    )
    if args.source == "api":
        stats = sync_from_api(out_dir=args.out, track_ids=ids, force=args.force)
    else:
        stats = sync_from_paths_dump(
            out_dir=args.out,
            track_ids=ids,
            force=args.force,
            dump_url=args.dump_url,
        )
    return 1 if stats["fail"] and not stats["ok"] and not stats["skip"] else 0


if __name__ == "__main__":
    sys.exit(main())
