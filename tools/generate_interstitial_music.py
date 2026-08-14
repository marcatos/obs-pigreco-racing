"""Compose original interstitial music loops (melodic motifs, not pads).

Generates short loopable songs for Starting Soon / Lobby / BRB / Ending:
melody + chords + bass + light percussion, 100% algorithmic / original to
this repo — safe for Twitch (no Pixabay / library catalog matches).

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
# ~64 bars @ 100 BPM ≈ 153.6s — long enough to loop without feeling like a 4-bar stub
DURATION_S = 96.0


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def note_env(t: float, dur: float, attack: float = 0.01, release: float = 0.08) -> float:
    if t < 0.0 or t >= dur:
        return 0.0
    if t < attack:
        return t / attack
    if t > dur - release:
        return max(0.0, (dur - t) / release)
    return 1.0


def osc_saw(phase: float) -> float:
    # phase in [0, 1)
    return 2.0 * phase - 1.0


def osc_tri(phase: float) -> float:
    return 1.0 - 4.0 * abs(phase - 0.5)


def osc_square(phase: float, width: float = 0.5) -> float:
    return 1.0 if phase < width else -1.0


def soft_clip(x: float) -> float:
    return math.tanh(x * 1.15)


@dataclass(frozen=True)
class MotifSpec:
    """One original loopable track recipe."""

    title: str
    bpm: float
    root_midi: int  # e.g. 57 = A3
    # Scale degrees relative to root (major / minor / dorian-ish)
    scale: tuple[int, ...]
    # Chord roots as scale-degree indices into `scale` (length = bars in progression)
    chords: tuple[int, ...]
    # Melody as (degree_index_or_None, length_in_beats) — None = rest
    melody: tuple[tuple[int | None, float], ...]
    bass_octave: int  # relative octaves from root
    melody_octave: int
    swing: float  # 0..0.2
    kick_pattern: tuple[float, ...]  # beat positions in bar (0..4)
    hat_pattern: tuple[float, ...]
    brightness: float  # 0..1 lead tone
    energy: float  # 0..1 drums / bass drive
    seed: int


# Scale helpers: chromatic intervals from root
MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)
DORIAN = (0, 2, 3, 5, 7, 9, 10)
MIXOLYDIAN = (0, 2, 4, 5, 7, 9, 10)


BEDS: dict[str, MotifSpec] = {
    "starting-soon.mp3": MotifSpec(
        title="Grid Call — waiting motif",
        bpm=102.0,
        root_midi=50,  # D3
        scale=MINOR,
        chords=(0, 5, 3, 4),  # i – VI – iv – v
        melody=(
            (0, 1.0),
            (2, 1.0),
            (4, 1.5),
            (None, 0.5),
            (3, 1.0),
            (2, 1.0),
            (0, 2.0),
            (4, 1.0),
            (5, 1.0),
            (4, 1.0),
            (2, 1.0),
            (0, 2.0),
            (None, 2.0),
        ),
        bass_octave=-1,
        melody_octave=1,
        swing=0.06,
        kick_pattern=(0.0, 2.0),
        hat_pattern=(0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5),
        brightness=0.45,
        energy=0.55,
        seed=42026,
    ),
    "lobby.mp3": MotifSpec(
        title="Paddock Walk — soft lounge motif",
        bpm=88.0,
        root_midi=53,  # F3
        scale=DORIAN,
        chords=(0, 3, 4, 0),  # i – IV – V – i (dorian colour)
        melody=(
            (4, 1.5),
            (5, 0.5),
            (4, 1.0),
            (2, 1.0),
            (0, 2.0),
            (None, 1.0),
            (2, 1.0),
            (3, 1.0),
            (4, 2.0),
            (5, 1.0),
            (4, 1.0),
            (2, 2.0),
            (None, 1.0),
        ),
        bass_octave=-1,
        melody_octave=1,
        swing=0.10,
        kick_pattern=(0.0, 2.5),
        hat_pattern=(0.0, 1.0, 2.0, 3.0),
        brightness=0.35,
        energy=0.35,
        seed=42042,
    ),
    "brb.mp3": MotifSpec(
        title="Hold Lane — cool BRB motif",
        bpm=96.0,
        root_midi=48,  # C3
        scale=MIXOLYDIAN,
        chords=(0, 4, 5, 3),  # I – V – vi – IV
        melody=(
            (0, 0.5),
            (2, 0.5),
            (4, 1.0),
            (5, 1.0),
            (4, 1.0),
            (2, 1.0),
            (0, 1.0),
            (None, 1.0),
            (4, 0.5),
            (5, 0.5),
            (7, 1.0),
            (5, 1.0),
            (4, 2.0),
            (None, 2.0),
        ),
        bass_octave=-1,
        melody_octave=1,
        swing=0.04,
        kick_pattern=(0.0, 1.5, 2.0),
        hat_pattern=(0.5, 1.5, 2.5, 3.5),
        brightness=0.50,
        energy=0.45,
        seed=42077,
    ),
    "ending.mp3": MotifSpec(
        title="Checkered Warm — resolve motif",
        bpm=92.0,
        root_midi=55,  # G3
        scale=MAJOR,
        chords=(0, 3, 4, 0),  # I – IV – V – I
        melody=(
            (0, 1.0),
            (2, 1.0),
            (4, 2.0),
            (5, 1.0),
            (4, 1.0),
            (2, 1.0),
            (0, 1.0),
            (4, 2.0),
            (5, 1.0),
            (7, 1.0),
            (5, 1.0),
            (4, 3.0),
            (None, 1.0),
        ),
        bass_octave=-1,
        melody_octave=1,
        swing=0.05,
        kick_pattern=(0.0, 2.0),
        hat_pattern=(0.0, 1.0, 2.0, 2.5, 3.0),
        brightness=0.55,
        energy=0.40,
        seed=42111,
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
    """Triad in the scale: root, third, fifth (by scale steps)."""
    root = degree_midi(spec, chord_deg_idx, 0)
    third = degree_midi(spec, chord_deg_idx + 2, 0)
    fifth = degree_midi(spec, chord_deg_idx + 4, 0)
    return root, third, fifth


def expand_melody_events(
    melody: tuple[tuple[int | None, float], ...],
) -> list[tuple[float, float, int | None]]:
    """Return list of (start_beat, dur_beats, degree)."""
    events: list[tuple[float, float, int | None]] = []
    t = 0.0
    for deg, dur in melody:
        events.append((t, dur, deg))
        t += dur
    return events


def compose_motif(spec: MotifSpec) -> list[float]:
    """Render a loopable stereo-summed mono mix of the motif."""
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
    # Align melody loop to whole bars
    melody_bars = max(1, int(math.ceil(loop_beats / bar_beats)))
    melody_events = expand_melody_events(spec.melody)

    # Precompute phase accumulators via sample loop
    for i in range(n):
        t = i / SR
        bar_f = t / bar_s
        bar_i = int(bar_f)
        bar_phase = bar_f - bar_i  # 0..1 within bar
        beat_in_bar = bar_phase * bar_beats

        chord_idx = progression[bar_i % n_prog_bars]
        c_root, c_third, c_fifth = chord_midis(spec, chord_idx)

        # --- pads / chords (soft saw + sine) ---
        chord = 0.0
        for midi, w in ((c_root, 0.45), (c_third, 0.35), (c_fifth, 0.30)):
            hz = midi_to_hz(midi)
            ph = (t * hz) % 1.0
            tone = 0.55 * math.sin(2 * math.pi * ph) + 0.25 * osc_tri(ph)
            if spec.brightness > 0.4:
                tone += 0.12 * osc_saw(ph)
            chord += tone * w
        chord *= 0.22 * (0.85 + 0.15 * math.sin(2 * math.pi * 0.125 * t))

        # --- bass (rooted, with passing on off-beats) ---
        bass_midi = c_root + 12 * spec.bass_octave
        # slight rhythm: longer on beat 1, ghost on 3
        bass_gate = 1.0
        if 0.9 < beat_in_bar < 1.1 or 2.9 < beat_in_bar < 3.15:
            bass_gate = 0.55
        bhz = midi_to_hz(bass_midi)
        bph = (t * bhz) % 1.0
        bass = (
            0.7 * math.sin(2 * math.pi * bph)
            + 0.25 * osc_square(bph, 0.42)
        ) * bass_gate * (0.20 + 0.12 * spec.energy)

        # --- melody ---
        # Position within repeating melody loop (in beats)
        total_beats = t / beat_s
        mel_loop = total_beats % max(loop_beats, 1e-6)
        mel = 0.0
        for start, dur, deg in melody_events:
            if deg is None:
                continue
            # swing delay on off-beats
            swing_delay = 0.0
            if abs((start % 1.0) - 0.5) < 0.05:
                swing_delay = spec.swing * beat_s
            local_t = (mel_loop - start) * beat_s - swing_delay
            env = note_env(local_t, dur * beat_s, attack=0.012, release=0.09)
            if env <= 0.0:
                continue
            midi = degree_midi(spec, deg, spec.melody_octave)
            hz = midi_to_hz(midi)
            # slight vibrato
            hz *= 1.0 + 0.003 * math.sin(2 * math.pi * 5.2 * t)
            ph = (t * hz) % 1.0
            lead = 0.62 * math.sin(2 * math.pi * ph) + 0.28 * osc_tri(ph)
            if spec.brightness > 0.45:
                lead += 0.15 * math.sin(4 * math.pi * ph)
            mel += lead * env * 0.28

        # --- drums ---
        drums = 0.0
        # kick
        for kb in spec.kick_pattern:
            dt = (beat_in_bar - kb) * beat_s
            if 0.0 <= dt < 0.18:
                # decaying sine thump
                drums += math.sin(2 * math.pi * (85.0 - 40.0 * dt) * dt) * math.exp(
                    -dt * 28.0
                ) * (0.35 * spec.energy)
        # hats
        for hb in spec.hat_pattern:
            dt = (beat_in_bar - hb) * beat_s
            if 0.0 <= dt < 0.04:
                noise = rng.signed()
                drums += noise * math.exp(-dt * 90.0) * (0.08 + 0.06 * spec.brightness)

        sample = soft_clip(chord + bass + mel + drums)
        # loop-friendly fades at ends of render (not mid-phrase)
        fade = 2.5
        if t < fade:
            sample *= t / fade
        elif t > DURATION_S - fade:
            sample *= max(0.0, (DURATION_S - t) / fade)

        buf[i] = sample

    peak = max(abs(x) for x in buf) or 1.0
    target = 10 ** (-2.5 / 20.0)
    gain = target / peak
    out = [x * gain for x in buf]
    log.info(
        "composed '%s' bpm=%.0f bars≈%.0f in %.1fs",
        spec.title,
        spec.bpm,
        DURATION_S / bar_s,
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
    log.info(
        "start composing %d original melodic beds → %s",
        len(BEDS),
        args.out_dir,
    )
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
            log.info("[%d/%d] %s — %s …", i, len(BEDS), name, spec.title)
            samples = compose_motif(spec)
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
