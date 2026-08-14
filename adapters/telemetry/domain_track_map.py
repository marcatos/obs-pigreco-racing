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


_SVG_TOKEN_RE = re.compile(
    r"([MmZzLlHhVvCcSsQqTtAa])|([-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)"
)

# Parameter counts per command (repeating groups allowed).
_SVG_ARITY = {
    "M": 2,
    "m": 2,
    "L": 2,
    "l": 2,
    "H": 1,
    "h": 1,
    "V": 1,
    "v": 1,
    "C": 6,
    "c": 6,
    "S": 4,
    "s": 4,
    "Q": 4,
    "q": 4,
    "T": 2,
    "t": 2,
    "A": 7,
    "a": 7,
}


def svg_path_bbox(d: str) -> tuple[float, float, float, float] | None:
    """Axis-aligned bbox of an SVG path `d`, resolving relative commands."""
    tokens = _SVG_TOKEN_RE.findall(d or "")
    if not tokens:
        return None

    cx = cy = 0.0
    start_x = start_y = 0.0
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    cmd = ""
    nums: list[float] = []

    def mark(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        if x < min_x:
            min_x = x
        if y < min_y:
            min_y = y
        if x > max_x:
            max_x = x
        if y > max_y:
            max_y = y

    def flush() -> None:
        nonlocal cx, cy, start_x, start_y, cmd, nums
        if not cmd or cmd in ("Z", "z"):
            if cmd in ("Z", "z"):
                cx, cy = start_x, start_y
                mark(cx, cy)
            nums = []
            return
        arity = _SVG_ARITY.get(cmd)
        if not arity or len(nums) < arity:
            nums = []
            return
        i = 0
        first = True
        while i + arity <= len(nums):
            chunk = nums[i : i + arity]
            i += arity
            if cmd == "M":
                cx, cy = chunk[0], chunk[1]
                if first:
                    start_x, start_y = cx, cy
                    mark(cx, cy)
                    first = False
                else:
                    # Extra pairs after M are implicit LineTo
                    mark(cx, cy)
                # Subsequent pairs behave as L
                if i < len(nums):
                    cmd = "L"
                    arity = 2
                    first = False
                    continue
            elif cmd == "m":
                cx += chunk[0]
                cy += chunk[1]
                if first:
                    start_x, start_y = cx, cy
                    mark(cx, cy)
                    first = False
                else:
                    mark(cx, cy)
                if i < len(nums):
                    cmd = "l"
                    arity = 2
                    first = False
                    continue
            elif cmd == "L":
                cx, cy = chunk[0], chunk[1]
                mark(cx, cy)
            elif cmd == "l":
                cx += chunk[0]
                cy += chunk[1]
                mark(cx, cy)
            elif cmd == "H":
                cx = chunk[0]
                mark(cx, cy)
            elif cmd == "h":
                cx += chunk[0]
                mark(cx, cy)
            elif cmd == "V":
                cy = chunk[0]
                mark(cx, cy)
            elif cmd == "v":
                cy += chunk[0]
                mark(cx, cy)
            elif cmd == "C":
                mark(chunk[0], chunk[1])
                mark(chunk[2], chunk[3])
                cx, cy = chunk[4], chunk[5]
                mark(cx, cy)
            elif cmd == "c":
                mark(cx + chunk[0], cy + chunk[1])
                mark(cx + chunk[2], cy + chunk[3])
                cx += chunk[4]
                cy += chunk[5]
                mark(cx, cy)
            elif cmd == "S":
                mark(chunk[0], chunk[1])
                cx, cy = chunk[2], chunk[3]
                mark(cx, cy)
            elif cmd == "s":
                mark(cx + chunk[0], cy + chunk[1])
                cx += chunk[2]
                cy += chunk[3]
                mark(cx, cy)
            elif cmd == "Q":
                mark(chunk[0], chunk[1])
                cx, cy = chunk[2], chunk[3]
                mark(cx, cy)
            elif cmd == "q":
                mark(cx + chunk[0], cy + chunk[1])
                cx += chunk[2]
                cy += chunk[3]
                mark(cx, cy)
            elif cmd == "T":
                cx, cy = chunk[0], chunk[1]
                mark(cx, cy)
            elif cmd == "t":
                cx += chunk[0]
                cy += chunk[1]
                mark(cx, cy)
            elif cmd == "A":
                cx, cy = chunk[5], chunk[6]
                mark(cx, cy)
            elif cmd == "a":
                cx += chunk[5]
                cy += chunk[6]
                mark(cx, cy)
            first = False
        nums = []

    for kind, num in tokens:
        if kind:
            flush()
            cmd = kind
            nums = []
            if cmd in ("Z", "z"):
                flush()
        else:
            nums.append(float(num))
    flush()

    if min_x == float("inf"):
        return None
    return (min_x, min_y, max_x, max_y)


def path_viewbox(d: str, *, pad: float = 80.0) -> str:
    """SVG viewBox string that fully contains path `d` (relative-safe)."""
    bb = svg_path_bbox(d)
    if not bb:
        return "0 0 2000 1200"
    min_x, min_y, max_x, max_y = bb
    w = max(1.0, (max_x - min_x) + 2 * pad)
    h = max(1.0, (max_y - min_y) + 2 * pad)
    return f"{min_x - pad:.2f} {min_y - pad:.2f} {w:.2f} {h:.2f}"


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
