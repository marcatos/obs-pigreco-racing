#!/usr/bin/env python3
"""
Start local telemetry producer for PiGreco / S.Marcato broadcast chrome.

Modes:
  mock     — fake standings (UI / OBS smoke), no iRacing
  iracing  — live SDK bridge (replay or session)

Default: mock. Does not autostart from OBS (external process only).
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEL = ROOT / "adapters" / "telemetry"
log = logging.getLogger("pigreco.telemetry.start")


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), None)
    if not isinstance(level, int):
        raise SystemExit(f"Invalid --log-level: {level_name}")
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    p = argparse.ArgumentParser(description="Start PiGreco telemetry producer")
    p.add_argument(
        "mode",
        nargs="?",
        choices=("mock", "iracing"),
        default="mock",
        help="mock (default) or iracing",
    )
    p.add_argument("--log-level", default="INFO")
    return p.parse_known_args(argv)


def main(argv: list[str] | None = None) -> int:
    args, extra = parse_args(argv)
    configure_logging(args.log_level)
    t0 = time.perf_counter()
    script = TEL / ("mock_server.py" if args.mode == "mock" else "iracing_bridge.py")
    if not script.is_file():
        log.error("Producer missing path=%s", script)
        return 2

    cmd = [sys.executable, str(script), *extra]
    log.info("start mode=%s cmd=%s", args.mode, " ".join(cmd))
    log.info(
        "Overlay: enable telemetryEnabled in config panel, then eye on "
        "Overlay Broadcast Chrome. Docs: docs/TELEMETRY_BROADCAST.md"
    )
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT))
        code = int(proc.returncode)
    except KeyboardInterrupt:
        log.info("Interrupted")
        code = 0
    except OSError as exc:
        log.exception("Failed to start producer: %s", exc)
        return 1

    elapsed = time.perf_counter() - t0
    log.info("end mode=%s exit=%d duration=%.2fs", args.mode, code, elapsed)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
