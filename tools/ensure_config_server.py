"""Ensure the PiGreco/Marcato config panel server is listening.

Idempotent: if 127.0.0.1:8766 already accepts connections, exit 0.
Otherwise start tools/config_server.py detached (no console window on Windows).

Used by:
- Start-ConfigPanel.bat
- OBS script obs/scripts/pigreco_config_autostart.py
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "tools" / "config_server.py"
LOG_DIR = ROOT / "logs"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ensure_config_server")


def port_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def find_python() -> str:
    # Prefer the interpreter running this file (matches venv / install).
    return sys.executable or "python"


def start_server(host: str, port: int) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "config_server.log"
    out = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 — kept for child lifetime
    out.write(f"\n--- ensure spawn {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    out.flush()

    cmd = [find_python(), str(SERVER), "--host", host, "--port", str(port)]
    creationflags = 0
    if sys.platform == "win32":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        creationflags = 0x00000008 | 0x00000200 | 0x08000000

    log.info("starting config server: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        close_fds=True,
    )
    return proc


def wait_until_up(host: str, port: int, timeout_s: float = 8.0) -> bool:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        if port_open(host, port):
            return True
        time.sleep(0.15)
    return False


def ensure(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    t0 = time.perf_counter()
    if port_open(host, port):
        log.info("config server already up on %s:%s (%.0f ms)", host, port, (time.perf_counter() - t0) * 1000)
        return 0

    if not SERVER.is_file():
        log.error("missing %s", SERVER)
        return 2

    proc = start_server(host, port)
    if wait_until_up(host, port):
        log.info(
            "config server ready pid=%s on %s:%s in %.0f ms",
            proc.pid,
            host,
            port,
            (time.perf_counter() - t0) * 1000,
        )
        return 0

    log.error(
        "config server did not become ready on %s:%s (pid=%s) — see logs/config_server.log",
        host,
        port,
        proc.pid,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
    )
    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    # Avoid sticking around holding the parent's console on Windows when
    # invoked from OBS; ensure returns as soon as the port is up.
    return ensure(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
