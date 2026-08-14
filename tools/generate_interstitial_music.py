"""Generate original interstitial bed loops (no third-party samples).

Outputs MP3 beds for Starting Soon / BRB / Ending that are synthesized
locally — they cannot match Twitch/Audible Magic catalogs the way Pixabay
or SoundHelix tracks often do.

Requires: ffmpeg on PATH.
"""
from __future__ import annotations

import argparse
import logging
import math
import struct
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("interstitial-music")

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "audio" / "interstitials"
SR = 44100
DURATION_S = 90.0


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def _fade_envelope(i: int, n: int, fade: int) -> float:
    if i < fade:
        return i / fade
    if i >= n - fade:
        return (n - 1 - i) / fade
    return 1.0


def synthesize_bed(
    *,
    roots_hz: tuple[float, ...],
    pulse_hz: float,
    noise_amt: float,
    brightness: float,
    seed: int,
) -> list[float]:
    """Simple multi-oscillator pad + filtered noise. 100% original synthesis."""
    n = int(SR * DURATION_S)
    fade = int(SR * 2.5)
    samples: list[float] = [0.0] * n

    # Lightweight LCG for reproducible noise (no stdlib random module variance)
    state = seed & 0xFFFFFFFF

    def rnd() -> float:
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        return (state / 0xFFFFFFFF) * 2.0 - 1.0

    # One-pole lowpass state for noise
    noise_lp = 0.0
    noise_coeff = 0.02 + 0.06 * brightness

    for i in range(n):
        t = i / SR
        env = _fade_envelope(i, n, fade)
        # Slow breathing LFO (unique per seed via phase)
        breath = 0.72 + 0.28 * math.sin(2 * math.pi * pulse_hz * t + seed * 0.17)

        pad = 0.0
        for k, f0 in enumerate(roots_hz):
            # slight detune + octave partials
            det = 1.0 + (0.0015 * (k - 1))
            f = f0 * det
            # soft triangle-ish (no harsh square) + quiet sine
            phase = 2 * math.pi * f * t
            tri = (2 / math.pi) * math.asin(math.sin(phase))
            sine = math.sin(phase)
            fifth = math.sin(2 * math.pi * f * 1.498 * t) * 0.22
            pad += (0.55 * sine + 0.35 * tri + fifth) / (1.35 + 0.15 * k)

        pad /= max(1, len(roots_hz) * 0.85)

        nraw = rnd()
        noise_lp = noise_lp + noise_coeff * (nraw - noise_lp)
        noise = noise_lp * noise_amt * (0.5 + 0.5 * brightness)

        # very slow shimmer
        shimmer = 0.04 * math.sin(2 * math.pi * (0.05 + seed * 0.003) * t) * pad

        samples[i] = _clamp((pad * breath + noise + shimmer) * env * 0.38)

    # Peak normalize to ~-3 dBFS equivalent
    peak = max(abs(x) for x in samples) or 1.0
    target = 10 ** (-3.0 / 20.0)
    gain = target / peak
    return [x * gain for x in samples]


def write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        frames = bytearray()
        for x in samples:
            frames.extend(struct.pack("<h", int(_clamp(x) * 32767.0)))
        wf.writeframes(frames)


def wav_to_mp3(wav: Path, mp3: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(wav),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        "-ar",
        str(SR),
        str(mp3),
    ]
    t0 = time.perf_counter()
    subprocess.run(cmd, check=True)
    log.info("encoded %s in %.0f ms (%d bytes)", mp3.name, (time.perf_counter() - t0) * 1000, mp3.stat().st_size)


BEDS = {
    "starting-soon.mp3": dict(
        # dark carbon pulse — waiting grid (refreshed 2026-08)
        roots_hz=(52.0, 78.0, 104.0, 156.0),
        pulse_hz=0.075,
        noise_amt=0.11,
        brightness=0.32,
        seed=42026,
    ),
    "lobby.mp3": dict(
        # soft paddock hold — menus / garage
        roots_hz=(46.0, 69.0, 92.0, 138.0),
        pulse_hz=0.055,
        noise_amt=0.09,
        brightness=0.30,
        seed=42042,
    ),
    "brb.mp3": dict(
        # cooler hold — soft tension
        roots_hz=(48.0, 72.0, 96.0, 144.0),
        pulse_hz=0.058,
        noise_amt=0.10,
        brightness=0.27,
        seed=42077,
    ),
    "ending.mp3": dict(
        # slightly warmer resolve
        roots_hz=(61.0, 92.0, 122.0, 184.0),
        pulse_hz=0.048,
        noise_amt=0.07,
        brightness=0.44,
        seed=42111,
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
    )
    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    t_all = time.perf_counter()
    log.info("start generating %d original interstitial beds → %s", len(BEDS), args.out_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        log.error("ffmpeg not found on PATH — required to write MP3")
        return 1

    with tempfile.TemporaryDirectory(prefix="marcato-beds-") as tmp:
        tmp_path = Path(tmp)
        for i, (name, params) in enumerate(BEDS.items(), start=1):
            t0 = time.perf_counter()
            log.info("[%d/%d] synthesize %s …", i, len(BEDS), name)
            samples = synthesize_bed(**params)
            wav = tmp_path / (Path(name).stem + ".wav")
            write_wav(wav, samples)
            out = args.out_dir / name
            wav_to_mp3(wav, out)
            log.info(
                "[%d/%d] %s done in %.1fs",
                i,
                len(BEDS),
                name,
                time.perf_counter() - t0,
            )

    log.info(
        "done in %.1fs | wrote %s",
        time.perf_counter() - t_all,
        ", ".join(BEDS),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
