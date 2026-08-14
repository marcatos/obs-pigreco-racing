"""
Sync official iRacing track SVG layers into a local gitignored cache.

Credentials (never logged):
  env IRACING_EMAIL + IRACING_PASSWORD
  or adapters/telemetry/iracing_api.local.json

Usage:
  python adapters/telemetry/sync_iracing_track_maps.py [--track-id 449] [--force]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from iracing_members_auth import fetch_bytes, fetch_json, login_session

log = logging.getLogger("pigreco.telemetry.sync_track_maps")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "overlays" / "assets" / "tracks" / "iracing"
ASSETS_URL = "https://members-ng.iracing.com/data/track/assets"
LOCAL_CREDS = Path(__file__).resolve().parent / "iracing_api.local.json"

# Prefer these layer filenames when present (relative names from API).
PREFERRED_LAYERS = ("active", "track", "default", "background")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_credentials() -> tuple[str, str]:
    import os

    email = (os.environ.get("IRACING_EMAIL") or "").strip()
    password = os.environ.get("IRACING_PASSWORD") or ""
    if email and password:
        return email, password
    if LOCAL_CREDS.is_file():
        data = json.loads(LOCAL_CREDS.read_text(encoding="utf-8"))
        email = str(data.get("email") or "").strip()
        password = str(data.get("password") or "")
        if email and password:
            return email, password
    raise SystemExit(
        "Missing credentials. Set IRACING_EMAIL/IRACING_PASSWORD or copy "
        "iracing_api.example.json → iracing_api.local.json"
    )


def pick_layer(layers: dict[str, str]) -> tuple[str, str] | None:
    """Return (layer_key, relative_path) for best outline layer."""
    if not layers:
        return None
    lower_map = {str(k).lower(): (str(k), str(v)) for k, v in layers.items()}
    for pref in PREFERRED_LAYERS:
        if pref in lower_map:
            return lower_map[pref]
    # values sometimes ARE the filenames; keys are semantic
    first_key = next(iter(layers))
    return str(first_key), str(layers[first_key])


def resolve_svg_url(track_map_base: str, layer_rel: str) -> str:
    from urllib.parse import urljoin

    base = track_map_base if track_map_base.endswith("/") else track_map_base + "/"
    return urljoin(base, layer_rel.lstrip("/"))


def sync_tracks(
    *,
    out_dir: Path,
    track_ids: set[str] | None,
    force: bool,
) -> dict[str, int]:
    t0 = time.perf_counter()
    email, password = load_credentials()
    opener = login_session(email, password)
    log.info("Fetching track assets catalog")
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
            log.warning("[%d/%d] trackId=%s invalid asset entry", i, stats["total"], tid)
            continue
        svg_path = out_dir / f"{tid}.svg"
        meta_path = out_dir / f"{tid}.meta.json"
        if svg_path.is_file() and not force:
            stats["skip"] += 1
            if not meta_path.is_file():
                meta_path.write_text(
                    json.dumps({"offset": 0.0, "direction": 1}, indent=2) + "\n",
                    encoding="utf-8",
                )
            if i == 1 or i % 25 == 0 or i == stats["total"]:
                log.info(
                    "Progress %d/%d (%.0f%%) ok=%d skip=%d fail=%d",
                    i,
                    stats["total"],
                    100.0 * i / max(1, stats["total"]),
                    stats["ok"],
                    stats["skip"],
                    stats["fail"],
                )
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
            if b"<svg" not in svg[:500].lower() and b"<svg" not in svg.lower():
                # still write; some payloads may be gzip-ish — require svg tag
                text = svg.decode("utf-8", errors="replace")
                if "<svg" not in text.lower():
                    raise RuntimeError("response is not SVG")
                svg = text.encode("utf-8")
            svg_path.write_bytes(svg)
            if not meta_path.is_file() or force:
                meta_path.write_text(
                    json.dumps({"offset": 0.0, "direction": 1, "layer": rel}, indent=2)
                    + "\n",
                    encoding="utf-8",
                )
            stats["ok"] += 1
            log.info("[%d/%d] wrote %s (%d bytes)", i, stats["total"], svg_path.name, len(svg))
        except Exception as exc:  # noqa: BLE001
            stats["fail"] += 1
            log.error("[%d/%d] trackId=%s failed: %s", i, stats["total"], tid, exc)

    elapsed = time.perf_counter() - t0
    log.info(
        "Sync done in %.1fs — total=%d ok=%d skip=%d fail=%d out=%s",
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
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)
    _setup_logging(args.log_level)
    ids = {str(x).strip() for x in (args.track_ids or []) if str(x).strip()} or None
    log.info("Starting track map sync out=%s force=%s filter=%s", args.out, args.force, ids)
    stats = sync_tracks(out_dir=args.out, track_ids=ids, force=args.force)
    return 1 if stats["fail"] and not stats["ok"] and not stats["skip"] else 0


if __name__ == "__main__":
    sys.exit(main())
