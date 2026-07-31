"""Local HTTP server for PiGreco OBS Config Panel (Custom Browser Dock)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from write_config_js import VALUES, write_config_js  # noqa: E402

OVERLAYS = ROOT / "overlays"
PANEL = OVERLAYS / "config-panel.html"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("config_server")


def load_values() -> dict:
    return json.loads(VALUES.read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "PiGrecoConfig/1.0"

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - " + fmt, self.address_string(), *args)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def _bytes(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/config-panel.html"):
            data = PANEL.read_bytes()
            self._bytes(200, data, "text/html; charset=utf-8")
            return
        if path == "/api/config":
            self._json(200, {"ok": True, "config": load_values()})
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "service": "pigreco-config"})
            return
        # static assets for panel (logo)
        if path.startswith("/assets/"):
            rel = path[len("/assets/") :]
            file_path = (OVERLAYS / "assets" / rel).resolve()
            if not str(file_path).startswith(str((OVERLAYS / "assets").resolve())):
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            if not file_path.is_file():
                self._json(404, {"ok": False, "error": "not found"})
                return
            ctype = "application/octet-stream"
            if file_path.suffix == ".png":
                ctype = "image/png"
            elif file_path.suffix == ".svg":
                ctype = "image/svg+xml"
            elif file_path.suffix == ".css":
                ctype = "text/css"
            self._bytes(200, file_path.read_bytes(), ctype)
            return
        self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "invalid JSON"})
            return

        if path == "/api/config":
            cfg = body.get("config")
            if not isinstance(cfg, dict):
                self._json(400, {"ok": False, "error": "missing config object"})
                return
            # merge onto existing to preserve unknown keys
            current = load_values()
            current.update(cfg)
            t0 = time.perf_counter()
            write_config_js(current)
            ms = (time.perf_counter() - t0) * 1000
            log.info("config saved (%d keys) in %.0f ms", len(current), ms)
            self._json(
                200,
                {
                    "ok": True,
                    "saved": True,
                    "keys": len(current),
                    "hint": "In OBS: tasto destro su ogni Browser Source overlay → Refresh cache of current page",
                },
            )
            return

        self._json(404, {"ok": False, "error": "not found"})


def main() -> None:
    parser = argparse.ArgumentParser(description="PiGreco OBS config panel server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    if not PANEL.exists():
        raise SystemExit(f"Missing panel HTML: {PANEL}")
    if not VALUES.exists():
        raise SystemExit(f"Missing {VALUES}")

    # Ensure config.js is in sync at boot
    write_config_js()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    log.info("PiGreco Config Panel in ascolto su %s", url)
    log.info("OBS → Visualizza → Docks → Custom Browser Docks → URL = %s", url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("shutdown")
        httpd.server_close()


if __name__ == "__main__":
    main()
