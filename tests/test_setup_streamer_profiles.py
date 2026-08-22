"""Tests for setup_streamer profile selection."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from setup_streamer import DEFAULT_PROFILES, parse_profiles  # noqa: E402


def test_parse_profiles_default_pigreco_only():
    assert parse_profiles("") == DEFAULT_PROFILES
    assert parse_profiles("   ") == DEFAULT_PROFILES
    assert parse_profiles("pigreco") == ("pigreco",)


def test_parse_profiles_marcato_and_both():
    assert parse_profiles("marcato") == ("marcato",)
    assert parse_profiles("pigreco,marcato") == ("pigreco", "marcato")
    assert parse_profiles("marcato pigreco") == ("marcato", "pigreco")


def test_parse_profiles_dedupes():
    assert parse_profiles("pigreco,pigreco") == ("pigreco",)
