"""Generate showcase screenshots of PiGreco OBS overlay scenes."""
from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("showcase")

ROOT = Path(__file__).resolve().parents[1]
OVERLAYS = ROOT / "overlays"
OUT = ROOT / "showcase"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

SHOTS = [
    ("01-starting-soon.png", "starting-soon.html", "Starting Soon"),
    ("02-live-chrome.png", "showcase-live.html", "Live Race / Live Singolo chrome"),
    ("03-brb.png", "brb.html", "BRB"),
    ("04-ending.png", "ending.html", "Ending"),
]


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


def capture(html_name: str, out_png: Path) -> None:
    html = OVERLAYS / html_name
    if not html.exists():
        raise FileNotFoundError(html)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    # Chrome writes to --screenshot path; use absolute path
    cmd = [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--window-size=1920,1080",
        f"--screenshot={out_png.resolve()}",
        file_url(html),
    ]
    t0 = time.perf_counter()
    log.info("capturing %s -> %s", html_name, out_png.name)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
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


def write_index(rows: list[tuple[str, str]]) -> None:
    cards = "\n".join(
        f"""
    <figure>
      <img src="{name}" alt="{label}" width="960" />
      <figcaption>{label}</figcaption>
    </figure>"""
        for name, label in rows
    )
    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8" />
  <title>PiGreco Racing — OBS Pack Showcase</title>
  <style>
    :root {{ --bg:#080a0c; --text:#f7fafc; --green:#00c400; --blue:#009fe5; --muted:#a7b1ba; }}
    body {{ margin:0; font-family: Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--text); }}
    header {{ padding:48px 32px 24px; max-width:1100px; margin:0 auto; }}
    h1 {{ margin:0 0 8px; font-size:2rem; }}
    p {{ color:var(--muted); max-width:62ch; line-height:1.5; }}
    .grid {{ display:grid; gap:28px; padding:16px 32px 64px; max-width:1100px; margin:0 auto; }}
    figure {{ margin:0; background:#11161a; border:1px solid rgba(255,255,255,.1); border-top:4px solid var(--green); }}
    img {{ display:block; width:100%; height:auto; }}
    figcaption {{ padding:12px 14px; font-weight:700; letter-spacing:.04em; text-transform:uppercase; color:var(--blue); }}
    code {{ color:var(--green); }}
  </style>
</head>
<body>
  <header>
    <h1>PiGreco Racing — OBS Pack</h1>
    <p>
      Showcase delle scene overlay (1920×1080). Per personalizzare nick/handle modifica
      <code>overlays/config.js</code> (template in <code>config.example.js</code>),
      poi esegui <code>python tools/setup_streamer.py --username tuo_nick</code>.
    </p>
  </header>
  <div class="grid">{cards}
  </div>
</body>
</html>
"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    log.info("wrote showcase/index.html")


def main() -> None:
    started = time.perf_counter()
    if not CHROME.exists():
        raise SystemExit(f"Chrome not found at {CHROME}")
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str]] = []
    for filename, html_name, label in SHOTS:
        out = OUT / filename
        capture(html_name, out)
        rows.append((filename, label))
    write_index(rows)
    log.info(
        "showcase complete: %d shots in %.1fs -> %s",
        len(rows),
        time.perf_counter() - started,
        OUT,
    )


if __name__ == "__main__":
    main()
