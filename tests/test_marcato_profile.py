from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from write_config_js import write_config_js


def test_write_config_js_marcato_root(tmp_path=None):
    root = ROOT / "overlays-marcato"
    assert (root / "config.values.json").is_file()
    out = write_config_js(overlay_root=root)
    assert out == root / "config.js"
    text = out.read_text(encoding="utf-8")
    assert "window.PIGRECO_CONFIG" in text
    data = json.loads((root / "config.values.json").read_text(encoding="utf-8"))
    assert data.get("sponsorsEnabled") is False
    assert "42" in str(data.get("raceNumber", "42"))
    assert "pigreco" not in data.get("teamName", "").lower()
