"""Ensure Session Director (+ telemetry bridge) are running.

Idempotent: if director is already alive, exit 0. Otherwise start
``adapters/obs_flag_director/director.py`` detached (no console on Windows).
Also starts the iRacing telemetry bridge on :8765 when nothing is listening.

Used by OBS Lua ``pigreco_config_autostart.lua`` via silent VBS launcher.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTOR = ROOT / "adapters" / "obs_flag_director" / "director.py"
TELEMETRY = ROOT / "tools" / "start_telemetry.py"
LOG_DIR = ROOT / "logs"
PID_FILE = LOG_DIR / "session_director.pid"
TELEM_PORT = 8765

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ensure_session_director")


def find_python() -> str:
    return sys.executable or "python"


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except SystemError:
        return False
    return True


def read_pid() -> int | None:
    try:
        raw = PID_FILE.read_text(encoding="utf-8").strip()
        return int(raw)
    except (OSError, ValueError):
        return None


def write_pid(pid: int) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(f"{pid}\n", encoding="utf-8")


def port_listening(port: int) -> bool:
    """True if something LISTENs on TCP port (no bare connect → no WS spam)."""
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        out = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            **kwargs,
        ).stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return False
    tok = f":{int(port)}"
    for line in out.splitlines():
        upper = line.upper()
        if "LISTENING" not in upper or "UDP" in upper:
            continue
        if tok in line:
            return True
    return False


def director_running() -> bool:
    pid = read_pid()
    if pid is not None and pid_alive(pid):
        return True
    if sys.platform != "win32":
        return False
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" |"
                " Where-Object { $_.CommandLine -match 'obs_flag_director\\\\director' } |"
                " Select-Object -First 1 -ExpandProperty ProcessId",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )
        raw = (proc.stdout or "").strip()
        if raw.isdigit():
            write_pid(int(raw))
            return True
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.debug("director process scan failed: %s", exc)
    return False


def _spawn_detached(cmd: list[str], log_name: str) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / log_name
    out = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 — child lifetime
    out.write(f"\n--- ensure spawn {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    out.flush()
    creationflags = 0
    if sys.platform == "win32":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        creationflags = 0x00000008 | 0x00000200 | 0x08000000
    log.info("starting: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        close_fds=True,
    )


def ensure_telemetry() -> None:
    if port_listening(TELEM_PORT):
        log.info("telemetry already listening on :%d", TELEM_PORT)
        return
    if not TELEMETRY.is_file():
        log.warning("missing %s — skip telemetry ensure", TELEMETRY)
        return
    _spawn_detached([find_python(), str(TELEMETRY), "iracing"], "telemetry_autostart.log")
    deadline = time.perf_counter() + 8.0
    while time.perf_counter() < deadline:
        if port_listening(TELEM_PORT):
            log.info("telemetry ready on :%d", TELEM_PORT)
            return
        time.sleep(0.2)
    log.warning(
        "telemetry did not bind :%d in time — see logs/telemetry_autostart.log",
        TELEM_PORT,
    )


def ensure_director() -> int:
    t0 = time.perf_counter()
    if director_running():
        log.info(
            "session director already running (%.0f ms)",
            (time.perf_counter() - t0) * 1000,
        )
        ensure_telemetry()
        return 0

    if not DIRECTOR.is_file():
        log.error("missing %s", DIRECTOR)
        return 2

    cfg_dir = ROOT / "adapters" / "obs_flag_director"
    local = cfg_dir / "config.local.json"
    example = cfg_dir / "config.example.json"
    if not local.is_file() and example.is_file():
        local.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        log.info(
            "created %s from example — set dryRun=false for live scene switches",
            local.name,
        )

    proc = _spawn_detached([find_python(), str(DIRECTOR)], "session_director.log")
    write_pid(proc.pid)
    time.sleep(0.8)
    if not pid_alive(proc.pid):
        log.error(
            "session director exited early (pid=%s) — is OBS WebSocket up? "
            "see logs/session_director.log",
            proc.pid,
        )
        return 1

    log.info(
        "session director started pid=%s in %.0f ms",
        proc.pid,
        (time.perf_counter() - t0) * 1000,
    )
    ensure_telemetry()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
    )
    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    return ensure_director()


if __name__ == "__main__":
    raise SystemExit(main())
