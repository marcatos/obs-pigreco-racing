#!/usr/bin/env python3
"""Print OBS WebSocket readiness checklist (no secrets).

Does not read OBS password. Use OBS → Tools → WebSocket Server Settings
→ Show Connect Info for password / QR.
"""
from __future__ import annotations

import argparse
import logging
import socket
import sys
import time
from pathlib import Path

log = logging.getLogger("pigreco.obs_ws_check")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 4455


def lan_ipv4s() -> list[str]:
    found: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in found:
                found.append(ip)
    except OSError as exc:
        log.debug("getaddrinfo failed: %s", exc)
    # UDP trick: discover preferred outbound interface
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127.") and ip not in found:
            found.insert(0, ip)
    except OSError as exc:
        log.debug("outbound probe failed: %s", exc)
    return found


def port_open(host: str, port: int, *, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    t0 = time.perf_counter()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("OBS WebSocket checklist starting (port=%d)", args.port)
    ips = lan_ipv4s()
    if ips:
        log.info("LAN IPv4 candidates for VirtualDeck host field: %s", ", ".join(ips))
    else:
        log.warning("Could not detect LAN IPv4 — check ipconfig / Wi-Fi")

    local = port_open("127.0.0.1", args.port)
    if local:
        log.info("Port %d accepts TCP on 127.0.0.1 — OBS WebSocket likely enabled", args.port)
    else:
        log.warning(
            "Port %d closed on 127.0.0.1 — enable Tools → WebSocket Server Settings in OBS",
            args.port,
        )

    for ip in ips[:3]:
        ok = port_open(ip, args.port)
        log.info("LAN probe %s:%d → %s", ip, args.port, "open" if ok else "closed/filtered")

    doc = ROOT / "docs" / "OBS_VIRTUALDECK.md"
    log.info("Operator guide: %s", doc)
    log.info(
        "Done in %.0f ms — copy password from OBS Connect Info (never commit it)",
        (time.perf_counter() - t0) * 1000,
    )
    return 0 if local else 1


if __name__ == "__main__":
    raise SystemExit(main())
