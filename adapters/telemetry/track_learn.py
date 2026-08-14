"""Self-learn track polyline from focus car samples (adapter-side IO)."""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Any

from domain_track_map import downsample_polyline, normalize_track_id

log = logging.getLogger("pigreco.telemetry.track_learn")

DEFAULT_LEARNED_DIR = Path(__file__).resolve().parent / "tracks_learned"
DEFAULT_OVERLAY_LEARNED = (
    Path(__file__).resolve().parents[2] / "overlays" / "assets" / "tracks" / "learned"
)


class TrackLearner:
    """Accumulate (distPct-ordered) normalized x,y samples for a track id."""

    def __init__(
        self,
        *,
        learned_dir: Path | None = None,
        overlay_dir: Path | None = None,
        min_samples: int = 40,
    ) -> None:
        self.learned_dir = learned_dir or DEFAULT_LEARNED_DIR
        self.overlay_dir = overlay_dir or DEFAULT_OVERLAY_LEARNED
        self.min_samples = min_samples
        self._track_id: str | None = None
        self._samples: list[tuple[float, float, float]] = []  # dist, x, y
        self._x = 0.5
        self._y = 0.5
        self._last_dist: float | None = None
        self._last_flush = 0.0

    def reset(self) -> None:
        self._samples.clear()
        self._last_dist = None
        self._x = 0.5
        self._y = 0.5

    def set_track(self, track_id: str | None, track_name: str | None) -> None:
        tid = normalize_track_id(track_id or track_name)
        if tid != self._track_id:
            if self._track_id and len(self._samples) >= self.min_samples:
                self.flush()
            self._track_id = tid
            self.reset()
            log.info("Track learner armed trackId=%s", tid)

    def sample(
        self,
        *,
        dist_pct: float | None,
        speed_mps: float | None,
        yaw_rad: float | None,
        dt_s: float = 0.1,
    ) -> None:
        if self._track_id is None or dist_pct is None:
            return
        try:
            d = float(dist_pct) % 1.0
        except (TypeError, ValueError):
            return

        # Dead-reckon in normalized space from speed + yaw when available.
        if isinstance(speed_mps, (int, float)) and isinstance(yaw_rad, (int, float)):
            # Scale: ~80 m/s around a ~0.4 radius track ≈ gentle motion in unit box
            step = float(speed_mps) * float(dt_s) * 0.0025
            self._x += step * math.cos(float(yaw_rad))
            self._y += step * math.sin(float(yaw_rad))
            self._x = min(0.95, max(0.05, self._x))
            self._y = min(0.95, max(0.05, self._y))
        else:
            # Fallback: place on a circle from distPct alone (still learnable shape later)
            a = 2 * math.pi * d
            self._x = 0.5 + 0.4 * math.cos(a)
            self._y = 0.5 + 0.28 * math.sin(a)

        if self._last_dist is not None and abs(d - self._last_dist) < 0.002:
            return
        self._last_dist = d
        self._samples.append((d, self._x, self._y))
        if len(self._samples) > 2000:
            self._samples = self._samples[-1500:]

        now = time.monotonic()
        if len(self._samples) >= self.min_samples and (now - self._last_flush) > 15.0:
            self.flush()

    def flush(self) -> Path | None:
        if not self._track_id or len(self._samples) < self.min_samples:
            return None
        ordered = sorted(self._samples, key=lambda t: t[0])
        # One point per coarse dist bucket
        buckets: dict[int, tuple[float, float]] = {}
        for d, x, y in ordered:
            b = int(d * 100)
            buckets[b] = (x, y)
        pts = [buckets[k] for k in sorted(buckets)]
        pts = downsample_polyline(pts, max_points=100)
        payload: dict[str, Any] = {
            "trackId": self._track_id,
            "points": [{"x": x, "y": y} for x, y in pts],
            "sampleCount": len(self._samples),
        }
        for folder in (self.learned_dir, self.overlay_dir):
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{self._track_id}.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            log.info(
                "Wrote learned track path=%s points=%d samples=%d",
                path,
                len(pts),
                len(self._samples),
            )
        self._last_flush = time.monotonic()
        return self.overlay_dir / f"{self._track_id}.json"
