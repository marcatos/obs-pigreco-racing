"""Generate OBS stinger WebM (VP9 + alpha) for PiGreco or S.Marcato 42.

Profiles:
  pigreco  — green/blue edge wipe + π logo → overlays/stinger/pigreco-stinger.webm
  marcato  — dual-blade carbon wipe + ice edges + rosso 42 mark
             → overlays-marcato/stinger/marcato-stinger.webm

Usage:
  python tools/generate_stinger.py --profile marcato
  python tools/generate_stinger.py --profile pigreco
  python tools/generate_stinger.py --profile marcato --with-whoosh
"""

from __future__ import annotations

import argparse
import logging
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]

W, H = 1920, 1080
FPS = 30
DURATION_S = 0.85
FRAME_COUNT = max(2, int(round(FPS * DURATION_S)))

log = logging.getLogger("stinger")


def ease_in_out(t: float) -> float:
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


# --- PiGreco (classic L→R) -------------------------------------------------

PGR_BG = (8, 10, 12, 255)
PGR_GREEN = (0, 196, 0, 255)
PGR_BLUE = (0, 159, 229, 255)


def pigreco_cover(t: float) -> tuple[int, int]:
    if t <= 0.5:
        p = ease_in_out(t / 0.5)
        return 0, int(round(W * p))
    p = ease_in_out((t - 0.5) / 0.5)
    return int(round(W * p)), W


def pigreco_logo_opacity(t: float) -> float:
    if t < 0.22:
        return 0.0
    if t < 0.38:
        return (t - 0.22) / 0.16
    if t <= 0.55:
        return 1.0
    if t < 0.72:
        return 1.0 - (t - 0.55) / 0.17
    return 0.0


def render_pigreco(logo: Image.Image, t: float) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    left, right = pigreco_cover(t)
    if right <= left:
        return canvas
    slab = Image.new("RGBA", (right - left, H), PGR_BG)
    draw = ImageDraw.Draw(slab)
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

    op = pigreco_logo_opacity(t)
    if op > 0.01:
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
        colored = logo.copy()
        if op < 0.999:
            bands = list(colored.split())
            if len(bands) == 4:
                a = bands[3].point(lambda p: int(p * op))
                colored = Image.merge("RGBA", (*bands[:3], a))
        lw, lh = colored.size
        canvas.alpha_composite(colored, (W // 2 - lw // 2, H // 2 - lh // 2))
    return canvas


# --- Marcato dual-blade ----------------------------------------------------

MAR_BG = (8, 8, 10, 255)
MAR_ICE = (248, 248, 250, 255)
MAR_ICE_DIM = (200, 200, 208, 255)


def marcato_blade_widths(t: float) -> tuple[int, int]:
    """Return (left_blade_w, right_blade_w). Full cover when both == W/2."""
    half = W // 2
    if t <= 0.48:
        p = ease_out_cubic(t / 0.48)
        w = int(round(half * p))
        return w, w
    if t <= 0.55:
        return half, half
    p = ease_in_out((t - 0.55) / 0.45)
    w = int(round(half * (1 - p)))
    return w, w


def marcato_mark_opacity(t: float) -> float:
    if t < 0.28:
        return 0.0
    if t < 0.42:
        return (t - 0.28) / 0.14
    if t <= 0.58:
        return 1.0
    if t < 0.74:
        return 1.0 - (t - 0.58) / 0.16
    return 0.0


def marcato_mark_scale(t: float) -> float:
    if t < 0.35:
        return 0.82
    if t < 0.5:
        return 0.82 + 0.22 * ease_out_cubic((t - 0.35) / 0.15)
    if t < 0.62:
        return 1.04
    return 1.04 + 0.08 * ((t - 0.62) / 0.38)


def _edge_gradient(draw: ImageDraw.ImageDraw, x0: int, width: int, height: int, *, inward: bool) -> None:
    """Ice → transparent edge band."""
    for i in range(width):
        mix = i / max(width - 1, 1)
        if not inward:
            mix = 1 - mix
        a = int(30 + 200 * (1 - mix))
        r = int(MAR_ICE_DIM[0] * (1 - mix) + MAR_ICE[0] * mix)
        g = int(MAR_ICE_DIM[1] * (1 - mix) + MAR_ICE[1] * mix)
        b = int(MAR_ICE_DIM[2] * (1 - mix) + MAR_ICE[2] * mix)
        draw.line([(x0 + i, 0), (x0 + i, height)], fill=(r, g, b, a))


def render_marcato(mark: Image.Image, t: float) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    left_w, right_w = marcato_blade_widths(t)
    edge = 36

    if left_w > 0:
        left = Image.new("RGBA", (left_w, H), MAR_BG)
        ld = ImageDraw.Draw(left)
        # subtle scanlines
        for y in range(0, H, 4):
            ld.line([(0, y), (left_w, y)], fill=(255, 255, 255, 6))
        band = min(edge, left_w)
        _edge_gradient(ld, left_w - band, band, H, inward=True)
        # thin accent line at blade tip
        ld.line([(left_w - 1, 0), (left_w - 1, H)], fill=(*MAR_ICE[:3], 220))
        canvas.paste(left, (0, 0), left)

    if right_w > 0:
        right = Image.new("RGBA", (right_w, H), MAR_BG)
        rd = ImageDraw.Draw(right)
        for y in range(0, H, 4):
            rd.line([(0, y), (right_w, y)], fill=(255, 255, 255, 6))
        band = min(edge, right_w)
        _edge_gradient(rd, 0, band, H, inward=False)
        rd.line([(0, 0), (0, H)], fill=(*MAR_ICE[:3], 220))
        canvas.paste(right, (W - right_w, 0), right)

    # Center gap flash when nearly closed
    gap = W - left_w - right_w
    if 0 < gap < 120:
        flash = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fd = ImageDraw.Draw(flash)
        a = int(50 * (1 - gap / 120))
        fd.rectangle([left_w, 0, W - right_w, H], fill=(248, 248, 250, a))
        canvas = Image.alpha_composite(canvas, flash)

    op = marcato_mark_opacity(t)
    if op > 0.01 and left_w + right_w >= W * 0.85:
        sc = marcato_mark_scale(t)
        mw, mh = mark.size
        size = (max(1, int(mw * sc)), max(1, int(mh * sc)))
        scaled = mark.resize(size, Image.Resampling.LANCZOS)
        if op < 0.999:
            bands = list(scaled.split())
            if len(bands) == 4:
                a = bands[3].point(lambda p: int(p * op))
                scaled = Image.merge("RGBA", (*bands[:3], a))
        # soft glow behind mark (ice, not red wash)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        cx, cy = W // 2, H // 2
        ga = int(35 * op)
        gd.ellipse([cx - 220, cy - 180, cx + 220, cy + 180], fill=(248, 248, 250, ga))
        glow = glow.filter(ImageFilter.GaussianBlur(28))
        canvas = Image.alpha_composite(canvas, glow)
        sw, sh = scaled.size
        canvas.alpha_composite(scaled, (cx - sw // 2, cy - sh // 2))

    return canvas


def prepare_pigreco_logo() -> Image.Image:
    path = ROOT / "overlays" / "assets" / "logo-pi-official.png"
    if not path.is_file():
        raise FileNotFoundError(path)
    logo = Image.open(path).convert("RGBA")
    target_w = 220
    ratio = target_w / logo.width
    return logo.resize((target_w, max(1, int(round(logo.height * ratio)))), Image.Resampling.LANCZOS)


def prepare_marcato_mark() -> Image.Image:
    path = ROOT / "overlays-marcato" / "assets" / "brand" / "mark42_rosso_corsa_transparent.png"
    if not path.is_file():
        raise FileNotFoundError(path)
    mark = Image.open(path).convert("RGBA")
    target_w = 280
    ratio = target_w / mark.width
    return mark.resize((target_w, max(1, int(round(mark.height * ratio)))), Image.Resampling.LANCZOS)


def write_frames(profile: str, frames_dir: Path) -> None:
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    if profile == "marcato":
        asset = prepare_marcato_mark()
        renderer = render_marcato
    else:
        asset = prepare_pigreco_logo()
        renderer = render_pigreco

    t0 = time.perf_counter()
    for i in range(FRAME_COUNT):
        t = i / (FRAME_COUNT - 1)
        frame = renderer(asset, t)
        frame.save(frames_dir / f"frame_{i:04d}.png", optimize=True)
        if i % 5 == 0 or i == FRAME_COUNT - 1:
            pct = 100.0 * (i + 1) / FRAME_COUNT
            elapsed = time.perf_counter() - t0
            rate = (i + 1) / elapsed if elapsed else 0
            eta = (FRAME_COUNT - i - 1) / rate if rate else 0
            log.info("frames %d/%d (%.0f%%) %.1f fps ETA %.1fs", i + 1, FRAME_COUNT, pct, rate, eta)
    log.info("wrote %d frames in %.0f ms", FRAME_COUNT, (time.perf_counter() - t0) * 1000)


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH")
    return exe


def make_whoosh(ffmpeg: str, path: Path) -> None:
    """Short stereo whoosh for stinger audio bed."""
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=140:duration={DURATION_S}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=420:duration={DURATION_S}",
        "-f",
        "lavfi",
        "-i",
        f"anoisesrc=color=pink:amplitude=0.04:duration={DURATION_S}",
        "-filter_complex",
        (
            "[0]volume=0.15,afade=t=in:d=0.05,afade=t=out:st=0.12:d=0.25[a];"
            "[1]volume=0.08,afade=t=in:st=0.35:d=0.04,afade=t=out:st=0.55:d=0.25[b];"
            "[2]highpass=f=800,volume=0.35,afade=t=in:d=0.03,afade=t=out:st=0.2:d=0.35[c];"
            "[a][b][c]amix=inputs=3:duration=first:dropout_transition=0,alimiter=limit=0.85"
        ),
        "-ar",
        "48000",
        "-ac",
        "2",
        str(path),
    ]
    subprocess.run(cmd, check=True, timeout=60)
    log.info("whoosh written %s", path.name)


def encode_webm(ffmpeg: str, frames_dir: Path, out_webm: Path, whoosh: Path | None) -> None:
    pattern = str(frames_dir / "frame_%04d.png")
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        str(FPS),
        "-i",
        pattern,
    ]
    if whoosh and whoosh.is_file():
        cmd += ["-i", str(whoosh)]
    cmd += [
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-b:v",
        "3M",
        "-auto-alt-ref",
        "0",
    ]
    if whoosh and whoosh.is_file():
        cmd += ["-c:a", "libopus", "-b:a", "96k", "-shortest"]
    else:
        cmd += ["-an"]
    cmd.append(str(out_webm))
    t0 = time.perf_counter()
    log.info("encoding %s", out_webm.name)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        log.error("ffmpeg stderr: %s", (proc.stderr or "")[-800:])
        raise RuntimeError(f"ffmpeg failed code={proc.returncode}")
    log.info(
        "encoded %s (%d KB) in %.0f ms",
        out_webm.name,
        out_webm.stat().st_size // 1024,
        (time.perf_counter() - t0) * 1000,
    )


def profile_paths(profile: str) -> tuple[Path, Path]:
    if profile == "marcato":
        d = ROOT / "overlays-marcato" / "stinger"
        return d, d / "marcato-stinger.webm"
    d = ROOT / "overlays" / "stinger"
    return d, d / "pigreco-stinger.webm"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate OBS stinger WebM")
    p.add_argument("--profile", choices=("pigreco", "marcato"), default="marcato")
    p.add_argument("--skip-encode", action="store_true")
    p.add_argument("--keep-frames", action="store_true")
    p.add_argument("--with-whoosh", action="store_true", help="Mux a short whoosh bed into the WebM")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper().replace("WARN", "WARNING")),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    total_t0 = time.perf_counter()
    stinger_dir, out_webm = profile_paths(args.profile)
    frames_dir = stinger_dir / "frames"
    log.info(
        "start profile=%s frames=%d fps=%d duration=%.2fs → %s",
        args.profile,
        FRAME_COUNT,
        FPS,
        DURATION_S,
        out_webm.name,
    )
    try:
        stinger_dir.mkdir(parents=True, exist_ok=True)
        write_frames(args.profile, frames_dir)
        if not args.skip_encode:
            ffmpeg = find_ffmpeg()
            whoosh_path = None
            if args.with_whoosh:
                whoosh_path = stinger_dir / "_whoosh.wav"
                make_whoosh(ffmpeg, whoosh_path)
            encode_webm(ffmpeg, frames_dir, out_webm, whoosh_path)
            if whoosh_path and whoosh_path.is_file():
                whoosh_path.unlink(missing_ok=True)
            if not args.keep_frames and frames_dir.exists():
                shutil.rmtree(frames_dir)
                log.info("removed temp frames")
        else:
            log.info("skip-encode: frames at %s", frames_dir)
    except Exception:
        log.exception("generate_stinger failed")
        return 1

    log.info("done in %.0f ms out=%s", (time.perf_counter() - total_t0) * 1000, out_webm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
