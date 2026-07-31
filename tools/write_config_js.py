"""Write overlays/config.js from config.values.json + config.runtime.js."""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("write_config_js")

ROOT = Path(__file__).resolve().parents[1]
OVERLAYS = ROOT / "overlays"
VALUES = OVERLAYS / "config.values.json"
RUNTIME = OVERLAYS / "config.runtime.js"
OUT = OVERLAYS / "config.js"


def write_config_js(values: dict | None = None) -> Path:
    if values is None:
        values = json.loads(VALUES.read_text(encoding="utf-8"))
    else:
        VALUES.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    runtime = RUNTIME.read_text(encoding="utf-8")
    body = json.dumps(values, ensure_ascii=False, indent=2)
    text = (
        "/* GENERATED from config.values.json — usa il pannello OBS o modifica il JSON */\n"
        "window.PIGRECO_CONFIG = "
        + body
        + ";\n\n"
        + runtime
    )
    OUT.write_text(text, encoding="utf-8")
    log.info("wrote %s (%d keys)", OUT.name, len(values))
    return OUT


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    write_config_js()
