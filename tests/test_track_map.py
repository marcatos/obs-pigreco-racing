"""Tests for track map path helpers and learner."""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEL = ROOT / "adapters" / "telemetry"
sys.path.insert(0, str(TEL))

from domain_track_map import (  # noqa: E402
    build_map_cars,
    generic_oval_points,
    normalize_track_id,
    point_on_polyline,
)
from track_learn import TrackLearner  # noqa: E402


def test_normalize_track_id():
    assert normalize_track_id("Monza GP") == "monza-gp"
    assert normalize_track_id(None) == "unknown"


def test_point_on_polyline_midpoint():
    pts = [(0.0, 0.0), (1.0, 0.0)]
    x, y = point_on_polyline(pts, 0.5)
    assert abs(x - 0.5) < 1e-6
    assert abs(y - 0.0) < 1e-6


def test_generic_oval_closed_loop():
    pts = generic_oval_points(32)
    assert len(pts) == 32
    x0, y0 = point_on_polyline(pts, 0.0)
    x1, y1 = point_on_polyline(pts, 1.0)
    assert math.hypot(x0 - x1, y0 - y1) < 0.05


def test_build_map_cars():
    rows = [
        {"carIdx": 1, "carNumber": "42", "pos": 1, "distPct": 0.1, "isFocus": True},
        {"carIdx": 2, "carNumber": "7", "pos": 2, "distPct": 0.2, "isFocus": False},
    ]
    cars = build_map_cars(rows, focus_car_idx=1)
    assert cars[0]["isFocus"] is True
    assert cars[1]["distPct"] == 0.2


def test_track_learner_flush(tmp_path: Path):
    learn = TrackLearner(learned_dir=tmp_path / "a", overlay_dir=tmp_path / "b", min_samples=5)
    learn.set_track("test-track", "Test Track")
    for i in range(10):
        learn.sample(dist_pct=i / 10.0, speed_mps=40.0, yaw_rad=i * 0.4, dt_s=0.1)
    path = learn.flush()
    assert path is not None
    assert path.is_file()
    data = path.read_text(encoding="utf-8")
    assert "test-track" in data
