"""Compose original interstitial music loops (melodic motifs).

Mood split (by design):
  - starting-soon / lobby → upbeat pre-race energy
  - brb / ending → calm, soft close / hold

100% algorithmic / original — Twitch-safe (no stock library catalogs).
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
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("interstitial-music")

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "audio" / "interstitials"
SR = 44100
DURATION_S = 80.0


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def note_env(t: float, dur: float, attack: float = 0.008, release: float = 0.06) -> float:
    if t < 0.0 or t >= dur:
        return 0.0
    if t < attack:
        return t / max(attack, 1e-6)
    if t > dur - release:
        return max(0.0, (dur - t) / max(release, 1e-6))
    return 1.0


def osc_saw(phase: float) -> float:
    return 2.0 * phase - 1.0


def osc_tri(phase: float) -> float:
    return 1.0 - 4.0 * abs(phase - 0.5)


def osc_square(phase: float, width: float = 0.5) -> float:
    return 1.0 if phase < width else -1.0


def soft_clip(x: float) -> float:
    return math.tanh(x)


@dataclass(frozen=True)
class MotifSpec:
    title: str
    mood: str  # "upbeat" | "calm"
    bpm: float
    root_midi: int
    scale: tuple[int, ...]
    chords: tuple[int, ...]
    melody: tuple[tuple[int | None, float], ...]
    bass_octave: int
    melody_octave: int
    swing: float
    kick_pattern: tuple[float, ...]
    snare_pattern: tuple[float, ...]
    hat_pattern: tuple[float, ...]
    brightness: float
    energy: float
    pad_amt: float
    lead_amt: float
    seed: int


MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)
MIXOLYDIAN = (0, 2, 4, 5, 7, 9, 10)
LYDIAN = (0, 2, 4, 6, 7, 9, 11)


BEDS: dict[str, MotifSpec] = {
    # —— UPBEAT: start / pre-race ——
    "starting-soon.mp3": MotifSpec(
        title="Lights Out — upbeat grid motif",
        mood="upbeat",
        bpm=126.0,
        root_midi=57,  # A3
        scale=MIXOLYDIAN,
        chords=(0, 4, 5, 3),  # I – V – vi – IV (pop energy)
        melody=(
            # punchy call-response hook
            (0, 0.5),
            (2, 0.5),
            (4, 0.5),
            (5, 0.5),
            (4, 1.0),
            (2, 1.0),
            (0, 0.5),
            (4, 0.5),
            (7, 1.0),
            (5, 1.0),
            (4, 1.0),
            (2, 1.0),
            (0, 1.0),
            (None, 0.5),
            (4, 0.5),
            (5, 0.5),
            (7, 0.5),
            (5, 1.0),
            (4, 1.0),
            (None, 1.0),
        ),
        bass_octave=-1,
        melody_octave=1,
        swing=0.02,
        kick_pattern=(0.0, 1.0, 2.0, 3.0),  # four-on-the-floor
        snare_pattern=(1.0, 3.0),
        hat_pattern=(0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5),
        brightness=0.72,
        energy=0.85,
        pad_amt=0.14,
        lead_amt=0.34,
        seed=71001,
    ),
    "lobby.mp3": MotifSpec(
        title="Formation Lap — upbeat paddock motif",
        mood="upbeat",
        bpm=120.0,
        root_midi=55,  # G3
        scale=MAJOR,
        chords=(0, 3, 4, 0, 5, 3, 4, 0),  # I–IV–V–I–vi–IV–V–I
        melody=(
            (4, 0.5),
            (5, 0.5),
            (7, 1.0),
            (5, 0.5),
            (4, 0.5),
            (2, 1.0),
            (0, 1.0),
            (2, 0.5),
            (4, 0.5),
            (5, 1.0),
            (4, 1.0),
            (None, 0.5),
            (2, 0.5),
            (4, 0.5),
            (5, 0.5),
            (7, 1.0),
            (9, 1.0),
            (7, 1.0),
            (5, 1.0),
            (4, 2.0),
            (None, 1.0),
        ),
        bass_octave=-1,
        melody_octave=1,
        swing=0.03,
        kick_pattern=(0.0, 0.75, 2.0, 2.5),
        snare_pattern=(1.0, 3.0),
        hat_pattern=(0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5),
        brightness=0.68,
        energy=0.78,
        pad_amt=0.12,
        lead_amt=0.32,
        seed=71002,
    ),
    # —— CALM: BRB / ending ——
    "brb.mp3": MotifSpec(
        title="Pit Lane Quiet — calm hold",
        mood="calm",
        bpm=68.0,
        root_midi=53,  # F3
        scale=MAJOR,
        chords=(0, 5, 3, 4),  # I – vi – IV – V (gentle)
        melody=(
            (4, 2.0),
            (5, 2.0),
            (4, 2.0),
            (2, 2.0),
            (0, 3.0),
            (None, 1.0),
            (2, 2.0),
            (4, 2.0),
            (5, 3.0),
            (None, 1.0),
        ),
        bass_octave=-1,
        melody_octave=1,
        swing=0.0,
        kick_pattern=(0.0,),  # soft pulse only on 1
        snare_pattern=(),
        hat_pattern=(0.0, 2.0),
        brightness=0.28,
        energy=0.18,
        pad_amt=0.32,
        lead_amt=0.16,
        seed=71003,
    ),
    "ending.mp3": MotifSpec(
        title="Cool Down Lap — calm resolve",
        mood="calm",
        bpm=62.0,
        root_midi=50,  # D3
        scale=LYDIAN,
        chords=(0, 3, 0, 4),  # I – IV – I – V (floating)
        melody=(
            (0, 2.0),
            (2, 2.0),
            (4, 3.0),
            (None, 1.0),
            (5, 2.0),
            (4, 2.0),
            (2, 2.0),
            (0, 4.0),
            (None, 2.0),
        ),
        bass_octave=-1,
        melody_octave=1,
        swing=0.0,
        kick_pattern=(),
        snare_pattern=(),
        hat_pattern=(0.0,),
        brightness=0.22,
        energy=0.10,
        pad_amt=0.38,
        lead_amt=0.14,
        seed=71004,
    ),
}


class LCG:
    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def rnd(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 0xFFFFFFFF

    def signed(self) -> float:
        return self.rnd() * 2.0 - 1.0


def degree_midi(spec: MotifSpec, degree_idx: int, octave: int) -> float:
    deg = degree_idx % len(spec.scale)
    oct_extra = degree_idx // len(spec.scale)
    return float(spec.root_midi + spec.scale[deg] + 12 * (octave + oct_extra))


def chord_midis(spec: MotifSpec, chord_deg_idx: int) -> tuple[float, float, float]:
    root = degree_midi(spec, chord_deg_idx, 0)
    third = degree_midi(spec, chord_deg_idx + 2, 0)
    fifth = degree_midi(spec, chord_deg_idx + 4, 0)
    return root, third, fifth


def expand_melody_events(
    melody: tuple[tuple[int | None, float], ...],
) -> list[tuple[float, float, int | None]]:
    events: list[tuple[float, float, int | None]] = []
    t = 0.0
    for deg, dur in melody:
        events.append((t, dur, deg))
        t += dur
    return events


def compose_motif(spec: MotifSpec) -> list[float]:
    t0 = time.perf_counter()
    n = int(SR * DURATION_S)
    buf = [0.0] * n
    rng = LCG(spec.seed)

    beat_s = 60.0 / spec.bpm
    bar_beats = 4.0
    bar_s = beat_s * bar_beats
    progression = spec.chords
    n_prog_bars = len(progression)
    loop_beats = sum(d for _, d in spec.melody)
    melody_events = expand_melody_events(spec.melody)
    upbeat = spec.mood == "upbeat"

    for i in range(n):
        t = i / SR
        bar_f = t / bar_s
        bar_i = int(bar_f)
        bar_phase = bar_f - bar_i
        beat_in_bar = bar_phase * bar_beats

        chord_idx = progression[bar_i % n_prog_bars]
        c_root, c_third, c_fifth = chord_midis(spec, chord_idx)

        # --- harmonic pad / stabs ---
        chord = 0.0
        for midi, w in ((c_root, 0.50), (c_third, 0.38), (c_fifth, 0.32)):
            hz = midi_to_hz(midi + (12 if upbeat else 0))
            ph = (t * hz) % 1.0
            if upbeat:
                # bright plucky stab envelope each half-bar
                stab_t = (beat_in_bar % 2.0) * beat_s
                stab = note_env(stab_t, 1.6 * beat_s, attack=0.004, release=0.35)
                tone = 0.45 * math.sin(2 * math.pi * ph) + 0.35 * osc_saw(ph)
                chord += tone * w * stab
            else:
                tone = 0.70 * math.sin(2 * math.pi * ph) + 0.20 * osc_tri(ph)
                chord += tone * w
        chord *= spec.pad_amt * (0.9 + 0.1 * math.sin(2 * math.pi * 0.08 * t))

        # --- bass ---
        bass_midi = c_root + 12 * spec.bass_octave
        bhz = midi_to_hz(bass_midi)
        bph = (t * bhz) % 1.0
        if upbeat:
            # pumping offbeat ghost + solid downs
            pump = 1.0
            frac = beat_in_bar % 1.0
            if 0.45 < frac < 0.55:
                pump = 0.35
            bass = (
                0.75 * math.sin(2 * math.pi * bph)
                + 0.30 * osc_square(bph, 0.38)
            ) * pump * (0.22 + 0.14 * spec.energy)
        else:
            bass = 0.55 * math.sin(2 * math.pi * bph) * 0.14

        # --- melody lead ---
        total_beats = t / beat_s
        mel_loop = total_beats % max(loop_beats, 1e-6)
        mel = 0.0
        for start, dur, deg in melody_events:
            if deg is None:
                continue
            swing_delay = 0.0
            if upbeat and abs((start % 1.0) - 0.5) < 0.05:
                swing_delay = spec.swing * beat_s
            local_t = (mel_loop - start) * beat_s - swing_delay
            atk = 0.006 if upbeat else 0.04
            rel = 0.05 if upbeat else 0.35
            env = note_env(local_t, dur * beat_s, attack=atk, release=rel)
            if env <= 0.0:
                continue
            midi = degree_midi(spec, deg, spec.melody_octave)
            hz = midi_to_hz(midi)
            if not upbeat:
                hz *= 1.0 + 0.0025 * math.sin(2 * math.pi * 4.5 * t)
            ph = (t * hz) % 1.0
            if upbeat:
                lead = (
                    0.50 * math.sin(2 * math.pi * ph)
                    + 0.30 * osc_square(ph, 0.45)
                    + 0.18 * math.sin(4 * math.pi * ph)
                )
            else:
                lead = 0.75 * math.sin(2 * math.pi * ph) + 0.20 * osc_tri(ph)
            mel += lead * env * spec.lead_amt

        # --- drums ---
        drums = 0.0
        for kb in spec.kick_pattern:
            dt = (beat_in_bar - kb) * beat_s
            if 0.0 <= dt < 0.16:
                amp = 0.42 * spec.energy if upbeat else 0.12 * spec.energy
                drums += (
                    math.sin(2 * math.pi * (90.0 - 55.0 * dt) * dt)
                    * math.exp(-dt * 32.0)
                    * amp
                )
        for sb in spec.snare_pattern:
            dt = (beat_in_bar - sb) * beat_s
            if 0.0 <= dt < 0.10:
                noise = rng.signed()
                body = math.sin(2 * math.pi * 180.0 * dt) * math.exp(-dt * 40.0)
                drums += (0.55 * noise * math.exp(-dt * 55.0) + 0.35 * body) * (
                    0.28 * spec.energy
                )
        for hb in spec.hat_pattern:
            dt = (beat_in_bar - hb) * beat_s
            if 0.0 <= dt < 0.035:
                noise = rng.signed()
                hat_amp = 0.10 if upbeat else 0.035
                drums += noise * math.exp(-dt * 100.0) * hat_amp * (
                    0.6 + 0.4 * spec.brightness
                )

        sample = soft_clip(chord + bass + mel + drums)
        fade = 2.0
        if t < fade:
            sample *= t / fade
        elif t > DURATION_S - fade:
            sample *= max(0.0, (DURATION_S - t) / fade)
        buf[i] = sample

    peak = max(abs(x) for x in buf) or 1.0
    target = 10 ** (-2.0 / 20.0) if upbeat else 10 ** (-3.0 / 20.0)
    gain = target / peak
    out = [x * gain for x in buf]
    log.info(
        "composed '%s' mood=%s bpm=%.0f in %.1fs",
        spec.title,
        spec.mood,
        spec.bpm,
        time.perf_counter() - t0,
    )
    return out


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
    log.info(
        "encoded %s in %.0f ms (%d bytes)",
        mp3.name,
        (time.perf_counter() - t0) * 1000,
        mp3.stat().st_size,
    )


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
    log.info("start composing %d beds → %s", len(BEDS), args.out_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        log.error("ffmpeg not found on PATH — required to write MP3")
        return 1

    with tempfile.TemporaryDirectory(prefix="marcato-beds-") as tmp:
        tmp_path = Path(tmp)
        for i, (name, spec) in enumerate(BEDS.items(), start=1):
            t0 = time.perf_counter()
            log.info("[%d/%d] %s — %s (%s) …", i, len(BEDS), name, spec.title, spec.mood)
            samples = compose_motif(spec)
            wav = tmp_path / (Path(name).stem + ".wav")
            write_wav(wav, samples)
            wav_to_mp3(wav, args.out_dir / name)
            log.info("[%d/%d] %s done in %.1fs", i, len(BEDS), name, time.perf_counter() - t0)

    log.info("done in %.1fs | wrote %s", time.perf_counter() - t_all, ", ".join(BEDS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
