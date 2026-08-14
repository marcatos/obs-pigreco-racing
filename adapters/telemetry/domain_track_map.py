"""Pure track-map path helpers (no IO)."""

from __future__ import annotations

import math
import re
from typing import Sequence


def normalize_track_id(name: str | None) -> str:
    if not name:
        return "unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return slug.strip("-") or "unknown"


def format_track_id(raw: object | None, fallback_name: str | None = None) -> str:
    """Prefer numeric WeekendInfo.TrackID; else slug from name."""
    if raw is not None:
        s = str(raw).strip()
        if s.isdigit():
            return str(int(s))
    if raw not in (None, ""):
        return normalize_track_id(str(raw))
    return normalize_track_id(fallback_name)


def apply_dist_offset(
    dist_pct: float, *, offset: float = 0.0, direction: int = 1
) -> float:
    """Map LapDistPct onto an SVG path with optional S/F offset and reverse."""
    t = float(dist_pct) % 1.0
    if t < 0:
        t += 1.0
    if int(direction) < 0:
        t = (1.0 - t) % 1.0
    t = (t + float(offset)) % 1.0
    if t < 0:
        t += 1.0
    return t


def generic_oval_points(n: int = 64) -> list[tuple[float, float]]:
    """Unit-ish oval in viewBox 0..1 (padding 0.08)."""
    pts: list[tuple[float, float]] = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x = 0.5 + 0.42 * math.cos(a)
        y = 0.5 + 0.28 * math.sin(a)
        pts.append((x, y))
    return pts


def downsample_polyline(
    points: Sequence[tuple[float, float]], max_points: int = 120
) -> list[tuple[float, float]]:
    if len(points) <= max_points:
        return [(float(x), float(y)) for x, y in points]
    step = len(points) / float(max_points)
    out: list[tuple[float, float]] = []
    i = 0.0
    while len(out) < max_points:
        idx = min(int(i), len(points) - 1)
        x, y = points[idx]
        out.append((float(x), float(y)))
        i += step
    return out


def _seg_lengths(points: Sequence[tuple[float, float]]) -> list[float]:
    lens: list[float] = []
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        lens.append(math.hypot(x1 - x0, y1 - y0))
    return lens


def point_on_polyline(
    points: Sequence[tuple[float, float]], dist_pct: float
) -> tuple[float, float]:
    """Map dist_pct in [0,1] along polyline (closed if first≈last)."""
    if not points:
        return (0.5, 0.5)
    if len(points) == 1:
        return (float(points[0][0]), float(points[0][1]))

    pts = list(points)
    # Close rings (3+ points) when endpoints are apart; keep open polylines as-is.
    if (
        len(pts) >= 3
        and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) > 1e-6
    ):
        pts = pts + [pts[0]]

    t = dist_pct % 1.0
    if t < 0:
        t += 1.0
    lens = _seg_lengths(pts)
    total = sum(lens) or 1.0
    target = t * total
    acc = 0.0
    for i, seg in enumerate(lens):
        if acc + seg >= target:
            if seg <= 1e-12:
                return (float(pts[i][0]), float(pts[i][1]))
            u = (target - acc) / seg
            x = pts[i][0] + u * (pts[i + 1][0] - pts[i][0])
            y = pts[i][1] + u * (pts[i + 1][1] - pts[i][1])
            return (float(x), float(y))
        acc += seg
    return (float(pts[-1][0]), float(pts[-1][1]))


def polyline_to_svg_path(points: Sequence[tuple[float, float]], *, scale: float = 100.0) -> str:
    if not points:
        return ""
    cmds = [f"M {points[0][0] * scale:.2f} {points[0][1] * scale:.2f}"]
    for x, y in points[1:]:
        cmds.append(f"L {x * scale:.2f} {y * scale:.2f}")
    cmds.append("Z")
    return " ".join(cmds)


def build_map_cars(
    rows: list[dict],
    *,
    focus_car_idx: int | None,
) -> list[dict]:
    """Build mapCars from standings-like rows that may include distPct."""
    out: list[dict] = []
    n = max(1, len(rows))
    for i, r in enumerate(rows):
        dist = r.get("distPct")
        if dist is None:
            # Fake spread by position if unknown
            pos = r.get("pos") or (i + 1)
            dist = ((int(pos) - 1) / n) % 1.0
        try:
            dist_f = float(dist) % 1.0
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "carIdx": r.get("carIdx"),
                "carNumber": str(r.get("carNumber") or ""),
                "distPct": dist_f,
                "isFocus": bool(
                    r.get("isFocus")
                    or (focus_car_idx is not None and r.get("carIdx") == focus_car_idx)
                ),
            }
        )
    return out
