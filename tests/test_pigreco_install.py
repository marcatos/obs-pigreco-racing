"""Tests for pigreco_install browser dock merge."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from pigreco_install import DOCK_TITLE, DOCK_URL, merge_browser_docks  # noqa: E402


def test_merge_browser_docks_adds_pigreco():
    out = json.loads(merge_browser_docks("[]"))
    assert any(d.get("title") == DOCK_TITLE for d in out)
    assert any(d.get("url") == DOCK_URL for d in out)


def test_merge_browser_docks_replaces_existing():
    existing = json.dumps([{"title": DOCK_TITLE, "url": "http://old/", "uuid": "x"}])
    out = json.loads(merge_browser_docks(existing))
    urls = [d.get("url") for d in out]
    assert DOCK_URL in urls
    assert "http://old/" not in urls
