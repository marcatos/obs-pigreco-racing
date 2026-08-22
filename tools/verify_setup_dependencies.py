"""Verify Python dependencies after Setup.ps1 pip install."""
from __future__ import annotations

import importlib
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("verify_setup_dependencies")

# (import name, pip distribution label)
REQUIRED = (
    ("PIL", "Pillow"),
    ("websockets", "websockets"),
    ("obsws_python", "obsws-python"),
    ("irsdk", "pyirsdk"),
    ("qrcode", "qrcode[pil]"),
)


def main() -> int:
    started = time.perf_counter()
    log.info("start dependency verification")
    missing: list[str] = []
    for module, label in REQUIRED:
        try:
            importlib.import_module(module)
            log.info("ok %s", label)
        except ImportError as exc:
            log.error("missing %s (%s): %s", label, module, exc)
            missing.append(label)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if missing:
        log.error("failed missing=%s total_ms=%d", ",".join(missing), elapsed_ms)
        return 1
    log.info("done all required imports ok total_ms=%d", elapsed_ms)
    return 0


if __name__ == "__main__":
    sys.exit(main())
