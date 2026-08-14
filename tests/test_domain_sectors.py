"""Unit tests for sector helpers (no iRacing SDK)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEL = ROOT / "adapters" / "telemetry"
sys.path.insert(0, str(TEL))

from domain_sectors import (  # noqa: E402
    SectorLapTracker,
    current_sector,
    delta_live_ms,
    normalize_sector_starts,
    sector_deltas_ms,
    sectors_payload,
)
from mock_server import build_tick  # noqa: E402


def test_normalize_sector_starts_from_yaml_shape():
    raw = [
        {"SectorNum": 0, "SectorStartPct": 0.0},
        {"SectorNum": 1, "SectorStartPct": 0.333},
        {"SectorNum": 2, "SectorStartPct": 0.667},
    ]
    starts = normalize_sector_starts(raw)
    assert starts[0] == 0.0
    assert len(starts) == 3
    assert current_sector(0.1, starts) == 1
    assert current_sector(0.5, starts) == 2
    assert current_sector(0.9, starts) == 3


def test_delta_live_and_sector_deltas():
    assert delta_live_ms(-0.234, True) == -234
    assert delta_live_ms(-0.234, False) is None
    assert sector_deltas_ms([30000, 31000], [29800, 31200]) == [200, -200]


def test_sector_tracker_latches_on_boundaries():
    tr = SectorLapTracker()
    tr.set_starts([0.0, 0.33, 0.66])
    # progress through S1
    tr.update(dist_pct=0.1, current_lap_ms=5000, lap=2, last_lap_ms=90000)
    # cross into S2
    snap = tr.update(dist_pct=0.34, current_lap_ms=28000, lap=2, last_lap_ms=90000)
    assert snap["sector"] == 2
    assert len(tr._open) == 1
    assert tr._open[0] == 28000
    # cross into S3
    tr.update(dist_pct=0.67, current_lap_ms=56000, lap=2, last_lap_ms=90000)
    assert len(tr._open) == 2
    # wrap / new lap finalizes with lastLapMs
    snap2 = tr.update(dist_pct=0.02, current_lap_ms=200, lap=3, last_lap_ms=90000)
    assert snap2["lastSectorsMs"] is not None
    assert len(snap2["lastSectorsMs"]) == 3
    assert sum(snap2["lastSectorsMs"]) == 90000
    assert snap2["sectorDeltaMs"] is not None


def test_build_tick_includes_sectors():
    tick = build_tick(40.0)
    assert isinstance(tick.get("sectors"), list)
    assert len(tick["sectors"]) == 3
    assert tick.get("sector") in (1, 2, 3)
    assert "deltaLiveMs" in tick
    assert tick.get("lastSectorsMs") is None or len(tick["lastSectorsMs"]) == 3
    assert sectors_payload([0.0, 0.5])[1]["num"] == 2
