"""Process official PiGreco assets: chroma-key black backgrounds."""
from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("assets")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "overlays" / "assets" / "official"
OUT = ROOT / "overlays" / "assets"


def key_black(im: Image.Image, threshold: int = 28, soft: int = 18) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r <= threshold and g <= threshold and b <= threshold:
                px[x, y] = (r, g, b, 0)
            elif r <= threshold + soft and g <= threshold + soft and b <= threshold + soft:
                alpha = int(a * (max(r, g, b) - threshold) / soft)
                px[x, y] = (r, g, b, max(0, min(255, alpha)))
    return im


def main() -> None:
    started = time.perf_counter()
    log.info("start processing official assets from %s", SRC)
    OUT.mkdir(parents=True, exist_ok=True)

    pairs = [
        ("logo-pigreco.png", "logo-pi-official.png", 40),
        ("logo.png", "logo-wordmark-official.png", 35),
        ("apple-touch-icon.png", "logo-pi-icon.png", 45),
    ]
    for src_name, dest_name, thr in pairs:
        t0 = time.perf_counter()
        keyed = key_black(Image.open(SRC / src_name), threshold=thr)
        dest = OUT / dest_name
        keyed.save(dest, "PNG")
        log.info(
            "wrote %s (%dx%d) in %.0f ms",
            dest.name,
            keyed.size[0],
            keyed.size[1],
            (time.perf_counter() - t0) * 1000,
        )

    hero_src = SRC / "hero-racing.jpg"
    hero_dst = OUT / "hero-racing.jpg"
    shutil.copy2(hero_src, hero_dst)
    log.info("copied hero-racing.jpg (%d bytes)", hero_dst.stat().st_size)

    # Keep primary logo path used by overlays pointing at official pi mark
    shutil.copy2(OUT / "logo-pi-official.png", OUT / "logo-pigreco.png")
    log.info("updated logo-pigreco.png from official pi mark")
    log.info("done in %.0f ms", (time.perf_counter() - started) * 1000)


if __name__ == "__main__":
    main()
