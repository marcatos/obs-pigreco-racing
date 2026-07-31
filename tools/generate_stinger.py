"""Generate PiGreco OBS stinger WebM (RGBA wipe + π logo).

Renders a short (~800ms) branded horizontal wipe to PNG frames, then encodes
WebM VP9 with alpha via ffmpeg for OBS Stinger transitions.

Usage:
  python tools/generate_stinger.py
  python tools/generate_stinger.py --log-level DEBUG
  python tools/generate_stinger.py --skip-encode   # frames only
"""
from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
STINGER_DIR = ROOT / "overlays" / "stinger"
LOGO_PATH = ROOT / "overlays" / "assets" / "logo-pi-official.png"
FRAMES_DIR = STINGER_DIR / "frames"
OUT_WEBM = STINGER_DIR / "pigreco-stinger.webm"

W, H = 1920, 1080
FPS = 30
DURATION_S = 0.8
FRAME_COUNT = max(2, int(round(FPS * DURATION_S)))

PGR_BG = (8, 10, 12, 255)
PGR_GREEN = (0, 196, 0, 255)
PGR_BLUE = (0, 159, 229, 255)

log = logging.getLogger("stinger")


def ease_in_out(t: float) -> float:
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


def cover_left(t: float) -> tuple[int, int]:
    """Return (opaque_left, opaque_right) for progress t in [0, 1].

    First half: cover L→R. Second half: reveal L→R (opaque slab slides off right).
    """
    if t <= 0.5:
        p = ease_in_out(t / 0.5)
        return 0, int(round(W * p))
    p = ease_in_out((t - 0.5) / 0.5)
    left = int(round(W * p))
    return left, W


def logo_opacity(t: float) -> float:
    # Visible around mid cover / hold / early reveal
    if t < 0.22:
        return 0.0
    if t < 0.38:
        return (t - 0.22) / 0.16
    if t <= 0.55:
        return 1.0
    if t < 0.72:
        return 1.0 - (t - 0.55) / 0.17
    return 0.0


def render_frame(logo: Image.Image, t: float) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    left, right = cover_left(t)
    if right > left:
        slab = Image.new("RGBA", (right - left, H), PGR_BG)
        draw = ImageDraw.Draw(slab)
        # Leading edge accent (right edge of slab during cover; left edge during reveal)
        edge_w = 28
        if t <= 0.5 and right < W:
            for x in range(edge_w):
                mix = x / max(edge_w - 1, 1)
                r = int(PGR_GREEN[0] * (1 - mix) + PGR_BLUE[0] * mix)
                g = int(PGR_GREEN[1] * (1 - mix) + PGR_BLUE[1] * mix)
                b = int(PGR_GREEN[2] * (1 - mix) + PGR_BLUE[2] * mix)
                a = int(80 + 175 * (1 - mix))
                draw.line([(slab.width - edge_w + x, 0), (slab.width - edge_w + x, H)], fill=(r, g, b, a))
        elif t > 0.5 and left > 0:
            for x in range(edge_w):
                mix = x / max(edge_w - 1, 1)
                r = int(PGR_BLUE[0] * (1 - mix) + PGR_GREEN[0] * mix)
                g = int(PGR_BLUE[1] * (1 - mix) + PGR_GREEN[1] * mix)
                b = int(PGR_BLUE[2] * (1 - mix) + PGR_GREEN[2] * mix)
                a = int(80 + 175 * mix)
                draw.line([(x, 0), (x, H)], fill=(r, g, b, a))
        canvas.paste(slab, (left, 0), slab)

        op = logo_opacity(t)
        if op > 0.01:
            # Soft green flash behind logo near midpoint
            if 0.4 <= t <= 0.6:
                flash = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                fd = ImageDraw.Draw(flash)
                flash_a = int(40 * (1 - abs(t - 0.5) / 0.1) * op)
                cx, cy = W // 2, H // 2
                for radius, alpha in ((420, flash_a), (260, flash_a + 20)):
                    fd.ellipse(
                        [cx - radius, cy - radius, cx + radius, cy + radius],
                        fill=(0, 196, 0, max(0, min(255, alpha))),
                    )
                canvas = Image.alpha_composite(canvas, flash)

            lw, lh = logo.size
            colored = logo.copy()
            if op < 0.999:
                # Multiply alpha channel
                bands = list(colored.split())
                if len(bands) == 4:
                    a = bands[3].point(lambda p: int(p * op))
                    colored = Image.merge("RGBA", (*bands[:3], a))
            canvas.alpha_composite(colored, (W // 2 - lw // 2, H // 2 - lh // 2))

    return canvas


def prepare_logo() -> Image.Image:
    if not LOGO_PATH.is_file():
        raise FileNotFoundError(f"logo missing: {LOGO_PATH}")
    logo = Image.open(LOGO_PATH).convert("RGBA")
    target_w = 220
    ratio = target_w / logo.width
    size = (target_w, max(1, int(round(logo.height * ratio))))
    return logo.resize(size, Image.Resampling.LANCZOS)


def write_frames(logo: Image.Image) -> list[Path]:
    if FRAMES_DIR.exists():
        shutil.rmtree(FRAMES_DIR)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    t0 = time.perf_counter()
    for i in range(FRAME_COUNT):
        t = i / (FRAME_COUNT - 1)
        frame = render_frame(logo, t)
        path = FRAMES_DIR / f"frame_{i:04d}.png"
        frame.save(path, optimize=True)
        paths.append(path)
        if i % 5 == 0 or i == FRAME_COUNT - 1:
            pct = 100.0 * (i + 1) / FRAME_COUNT
            elapsed = time.perf_counter() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (FRAME_COUNT - i - 1) / rate if rate > 0 else 0
            log.info(
                "frames %d/%d (%.0f%%) %.1f fps ETA %.1fs",
                i + 1,
                FRAME_COUNT,
                pct,
                rate,
                eta,
            )
    log.info(
        "wrote %d frames to %s in %.0f ms",
        len(paths),
        FRAMES_DIR,
        (time.perf_counter() - t0) * 1000,
    )
    return paths


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH — install ffmpeg or use --skip-encode")
    return exe


def encode_webm(ffmpeg: str) -> None:
    pattern = str(FRAMES_DIR / "frame_%04d.png")
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        pattern,
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-b:v",
        "2M",
        "-auto-alt-ref",
        "0",
        "-an",
        str(OUT_WEBM),
    ]
    t0 = time.perf_counter()
    log.info("encoding WebM via ffmpeg → %s", OUT_WEBM.name)
    log.debug("cmd: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        log.error("ffmpeg stderr: %s", (proc.stderr or "")[-800:])
        raise RuntimeError(f"ffmpeg failed code={proc.returncode}")
    size_kb = OUT_WEBM.stat().st_size // 1024
    log.info("encoded %s (%d KB) in %.0f ms", OUT_WEBM.name, size_kb, (time.perf_counter() - t0) * 1000)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate PiGreco OBS stinger WebM")
    p.add_argument("--skip-encode", action="store_true", help="Write PNG frames only")
    p.add_argument(
        "--keep-frames",
        action="store_true",
        help="Keep overlays/stinger/frames after encode",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARN", "WARNING", "ERROR"],
        help="Logging verbosity (default INFO)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    level = getattr(logging, args.log_level.upper().replace("WARN", "WARNING"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    total_t0 = time.perf_counter()
    log.info(
        "start generate_stinger frames=%d fps=%d duration=%.2fs canvas=%dx%d",
        FRAME_COUNT,
        FPS,
        DURATION_S,
        W,
        H,
    )
    try:
        STINGER_DIR.mkdir(parents=True, exist_ok=True)
        logo = prepare_logo()
        write_frames(logo)
        if not args.skip_encode:
            encode_webm(find_ffmpeg())
            if not args.keep_frames and FRAMES_DIR.exists():
                shutil.rmtree(FRAMES_DIR)
                log.info("removed temp frames dir")
        else:
            log.info("skip-encode: frames kept at %s", FRAMES_DIR)
    except Exception:
        log.exception("generate_stinger failed")
        log.info("total failed in %.0f ms", (time.perf_counter() - total_t0) * 1000)
        return 1

    log.info(
        "done ok out=%s total=%.0f ms",
        OUT_WEBM if OUT_WEBM.exists() else FRAMES_DIR,
        (time.perf_counter() - total_t0) * 1000,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
