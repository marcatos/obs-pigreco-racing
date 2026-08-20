"""Generate showcase screenshots of OBS overlay scenes (PiGreco + S.Marcato)."""
from __future__ import annotations

import argparse
import logging
import subprocess
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("showcase")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "showcase"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

PIGRECO_SHOTS = [
    ("01-starting-soon.png", "overlays", "starting-soon.html", "Starting Soon"),
    ("02-live-chrome.png", "overlays", "showcase-live.html", "Live Race / Live Singolo"),
    ("03-brb.png", "overlays", "brb.html?brbUntil=21:45", "BRB"),
    ("04-ending.png", "overlays", "ending.html", "Ending"),
]

MARCATO_SHOTS = [
    ("marcato-01-starting-soon.png", "overlays-marcato", "starting-soon.html", "Starting Soon"),
    ("marcato-02-live.png", "overlays-marcato", "showcase-live.html", "Live"),
    ("marcato-03-headcam.png", "overlays-marcato", "showcase-headcam.html", "Headcam"),
    ("marcato-04-lobby.png", "overlays-marcato", "showcase-lobby.html", "Lobby"),
    ("marcato-05-brb.png", "overlays-marcato", "brb.html?brbUntil=21:45", "BRB"),
    ("marcato-06-ending.png", "overlays-marcato", "ending.html", "Ending"),
    (
        "marcato-07-triple-frame.png",
        "overlays-marcato",
        "triple-frame.html?cam=1&badge=LIVE",
        "Triple frame (Replay / Rec)",
    ),
    (
        "marcato-08-replay-chrome.png",
        "overlays-marcato",
        "replay-chrome.html",
        "Replay Chrome",
    ),
]


def file_url(path: Path, query: str = "") -> str:
    uri = path.resolve().as_uri()
    if query:
        return uri + ("&" if "?" in uri else "?") + query.lstrip("?")
    return uri


def capture(overlay_dir: Path, html_spec: str, out_png: Path) -> None:
    html_name, _, query = html_spec.partition("?")
    html = overlay_dir / html_name
    if not html.exists():
        raise FileNotFoundError(html)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--window-size=1920,1080",
        f"--screenshot={out_png.resolve()}",
        "--virtual-time-budget=3500",
        file_url(html, query),
    ]
    t0 = time.perf_counter()
    log.info("capturing %s/%s -> %s", overlay_dir.name, html_name, out_png.name)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0:
        log.error("chrome stderr: %s", proc.stderr[-500:] if proc.stderr else "")
        raise RuntimeError(f"chrome failed for {html_name} code={proc.returncode}")
    if not out_png.exists() or out_png.stat().st_size < 1000:
        raise RuntimeError(f"screenshot missing or too small: {out_png}")
    log.info(
        "ok %s (%d KB) in %.0f ms",
        out_png.name,
        out_png.stat().st_size // 1024,
        (time.perf_counter() - t0) * 1000,
    )


def write_index(
    pigreco: list[tuple[str, str]],
    marcato: list[tuple[str, str]],
) -> None:
    def section(title: str, accent: str, rows: list[tuple[str, str]]) -> str:
        cards = "\n".join(
            f"""
    <figure style="border-top-color:{accent}">
      <img src="{name}" alt="{label}" width="960" loading="lazy" />
      <figcaption style="color:{accent}">{label}</figcaption>
    </figure>"""
            for name, label in rows
        )
        return f"""
  <header>
    <h2>{title}</h2>
  </header>
  <div class="grid">{cards}
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8" />
  <title>OBS Sim Racing Pack — Showcase</title>
  <style>
    :root {{
      --bg:#08080a; --text:#f8f8fa; --muted:#a8a8b0;
      --green:#00c400; --blue:#009fe5; --rosso:#e10600;
    }}
    body {{ margin:0; font-family: "Segoe UI", system-ui, sans-serif; background:var(--bg); color:var(--text); }}
    .hero {{ padding:48px 32px 16px; max-width:1100px; margin:0 auto; }}
    h1 {{ margin:0 0 8px; font-size:2rem; }}
    h2 {{ margin:32px 0 0; font-size:1.15rem; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); }}
    p {{ color:var(--muted); max-width:62ch; line-height:1.5; }}
    .grid {{ display:grid; gap:28px; padding:16px 32px 48px; max-width:1100px; margin:0 auto; }}
    figure {{ margin:0; background:#121216; border:1px solid rgba(255,255,255,.1); border-top:4px solid var(--green); }}
    img {{ display:block; width:100%; height:auto; }}
    figcaption {{ padding:12px 14px; font-weight:700; letter-spacing:.04em; text-transform:uppercase; }}
    code {{ color:var(--green); }}
  </style>
</head>
<body>
  <div class="hero">
    <h1>OBS Sim Racing Pack — Showcase</h1>
    <p>
      Anteprime overlay 1920×1080. Rigenera con
      <code>python tools/generate_showcase.py</code>.
    </p>
  </div>
  {section("PiGreco Racing", "var(--green)", pigreco)}
  {section("S.Marcato 42", "var(--rosso)", marcato)}
</body>
</html>
"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    log.info("wrote showcase/index.html")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("all", "pigreco", "marcato"),
        default="all",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARN", "ERROR"])
    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    started = time.perf_counter()
    if not CHROME.exists():
        raise SystemExit(f"Chrome not found at {CHROME}")
    OUT.mkdir(parents=True, exist_ok=True)

    pigreco_rows: list[tuple[str, str]] = []
    marcato_rows: list[tuple[str, str]] = []

    shots: list[tuple[str, str, str, str]] = []
    if args.profile in ("all", "pigreco"):
        shots.extend(PIGRECO_SHOTS)
    if args.profile in ("all", "marcato"):
        shots.extend(MARCATO_SHOTS)

    for filename, folder, html_name, label in shots:
        out = OUT / filename
        capture(ROOT / folder, html_name, out)
        if folder == "overlays":
            pigreco_rows.append((filename, label))
        else:
            marcato_rows.append((filename, label))

    # Keep existing gallery entries if regenerating only one profile
    if args.profile == "pigreco":
        for filename, _folder, _html, label in MARCATO_SHOTS:
            if (OUT / filename).is_file():
                marcato_rows.append((filename, label))
    if args.profile == "marcato":
        for filename, _folder, _html, label in PIGRECO_SHOTS:
            if (OUT / filename).is_file():
                pigreco_rows.append((filename, label))

    write_index(pigreco_rows, marcato_rows)
    log.info(
        "showcase complete: %d shots in %.1fs -> %s",
        len(pigreco_rows) + len(marcato_rows),
        time.perf_counter() - started,
        OUT,
    )


if __name__ == "__main__":
    main()
