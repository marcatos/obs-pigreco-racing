"""Cam device ID hygiene for generate_pack."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import generate_pack as gp  # noqa: E402


def test_streamcam_id_has_no_hash22_escape():
    assert "#22" not in gp.STREAMCAM_ID
    assert "vid_046d" in gp.STREAMCAM_ID
    assert "8&33ee287c" in gp.STREAMCAM_ID.lower()


def test_usbcam_id_matches_seat_cam():
    assert "#22" not in gp.USBCAM_ID
    assert "vid_0c6a" in gp.USBCAM_ID
    assert "9&1779791d" in gp.USBCAM_ID.lower()


def test_brio_and_creative_ids():
    assert "#22" not in gp.BRIO_ID
    assert "vid_046d" in gp.BRIO_ID
    assert "pid_085e" in gp.BRIO_ID
    assert "9&341f90e2" in gp.BRIO_ID.lower()
    assert "#22" not in gp.CREATIVE_ID
    assert "vid_041e" in gp.CREATIVE_ID
    assert "pid_40a9" in gp.CREATIVE_ID
    assert "b&938a461" in gp.CREATIVE_ID.lower()
