from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from write_config_js import OUT, OVERLAYS, VALUES, write_config_js


def _parsed_config_from_js(text: str) -> dict:
    prefix = "window.PIGRECO_CONFIG = "
    start = text.index(prefix) + len(prefix)
    end = text.index(";\n\n", start)
    return json.loads(text[start:end])


def test_write_config_js_marcato_root():
    root = ROOT / "overlays-marcato"
    assert (root / "config.values.json").is_file()
    out = write_config_js(overlay_root=root)
    assert out == root / "config.js"
    text = out.read_text(encoding="utf-8")
    assert "window.PIGRECO_CONFIG" in text
    js_cfg = _parsed_config_from_js(text)
    assert js_cfg.get("sponsorsEnabled") is False
    data = json.loads((root / "config.values.json").read_text(encoding="utf-8"))
    assert data.get("sponsorsEnabled") is False
    assert "42" in str(data.get("raceNumber", "42"))
    assert "pigreco" not in data.get("teamName", "").lower()


def test_marcato_theme_has_steel_tokens_not_pigreco():
    css = (ROOT / "overlays-marcato" / "assets" / "theme.css").read_text(encoding="utf-8")
    assert "--steel:" in css
    assert "--line:" in css
    assert "--panel:" in css
    assert "--font-display:" in css
    assert "--font-body:" in css
    assert "Orbitron" not in css
    assert "Space Grotesk" not in css
    assert "#00c400" not in css.lower()
    assert "#009fe5" not in css.lower()
    assert "Syne" in css
    assert "IBM Plex Sans" in css


def test_write_config_js_default_overlay_root():
    assert VALUES == OVERLAYS / "config.values.json"
    assert OUT == OVERLAYS / "config.js"
    out = write_config_js()
    assert out == ROOT / "overlays" / "config.js"
    assert out == OUT
