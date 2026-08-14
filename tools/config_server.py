"""Local HTTP server for PiGreco OBS Config Panel (Custom Browser Dock)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from write_config_js import VALUES, write_config_js  # noqa: E402

OVERLAYS = ROOT / "overlays"
PANEL = OVERLAYS / "config-panel.html"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766

PROFILES = {
    "pigreco": ROOT / "overlays",
    "marcato": ROOT / "overlays-marcato",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("config_server")


def resolve_overlay_root(query: dict | None = None) -> Path:
    profile: str | None = None
    if query:
        raw = query.get("profile")
        if raw:
            profile = raw[0] if isinstance(raw, list) else str(raw)
    key = (profile or "pigreco").strip().lower()
    if key not in PROFILES:
        key = "pigreco"
    return PROFILES[key]


def load_values(overlay_root: Path | None = None) -> dict:
    root = overlay_root or OVERLAYS
    values_path = root / "config.values.json"
    return json.loads(values_path.read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "PiGrecoConfig/1.0"

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - " + fmt, self.address_string(), *args)

    def _parsed_url(self):
        return urlparse(self.path)

    def _query(self) -> dict:
        return parse_qs(self._parsed_url().query, keep_blank_values=True)

    def _overlay_root(self) -> Path:
        return resolve_overlay_root(self._query())

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
        path = self._parsed_url().path
        if path in ("/", "/index.html", "/config-panel.html"):
            data = PANEL.read_bytes()
            self._bytes(200, data, "text/html; charset=utf-8")
            return
        if path == "/api/config":
            root = self._overlay_root()
            self._json(
                200,
                {
                    "ok": True,
                    "profile": next(k for k, v in PROFILES.items() if v == root),
                    "config": load_values(root),
                },
            )
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "service": "pigreco-config"})
            return
        # Overlay pack over HTTP (OBS Browser Source + WebSocket need http:// not file://)
        # /o/marcato/... -> overlays-marcato/
        # /o/overlays/... or /o/pigreco/... -> overlays/
        if path.startswith("/o/"):
            self._serve_overlay_pack(path)
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

    def _serve_overlay_pack(self, path: str) -> None:
        """Serve overlay HTML/JS/CSS so CEF can open ws://127.0.0.1:8765."""
        # path like /o/marcato/broadcast-chrome.html
        rest = path[len("/o/") :]
        if "/" not in rest:
            self._json(404, {"ok": False, "error": "not found"})
            return
        pack, rel = rest.split("/", 1)
        pack = pack.strip().lower()
        if pack in ("marcato",):
            root = PROFILES["marcato"]
        elif pack in ("overlays", "pigreco"):
            root = PROFILES["pigreco"]
        else:
            self._json(404, {"ok": False, "error": "unknown pack"})
            return
        if ".." in rel.replace("\\", "/").split("/"):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        file_path = (root / rel).resolve()
        root_resolved = root.resolve()
        if not str(file_path).startswith(str(root_resolved)) or not file_path.is_file():
            self._json(404, {"ok": False, "error": "not found"})
            return
        suffix = file_path.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
        }.get(suffix, "application/octet-stream")
        self._bytes(200, file_path.read_bytes(), ctype)

    def do_POST(self) -> None:
        path = self._parsed_url().path
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
            root = self._overlay_root()
            current = load_values(root)
            current.update(cfg)
            t0 = time.perf_counter()
            write_config_js(current, overlay_root=root)
            ms = (time.perf_counter() - t0) * 1000
            profile_key = next(k for k, v in PROFILES.items() if v == root)
            log.info(
                "config saved (%d keys) profile=%s in %.0f ms",
                len(current),
                profile_key,
                ms,
            )
            self._json(
                200,
                {
                    "ok": True,
                    "saved": True,
                    "profile": profile_key,
                    "keys": len(current),
                    "hint": (
                        f"Salvato profilo «{profile_key}» "
                        f"({root.name}/config.values.json). "
                        "In OBS: refresh cache delle Browser Source overlay del profilo."
                    ),
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

    # Ensure config.js is in sync at boot for each profile that has values JSON
    write_config_js()
    marcato_values = PROFILES["marcato"] / "config.values.json"
    if marcato_values.is_file():
        write_config_js(overlay_root=PROFILES["marcato"])

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    log.info("PiGreco Config Panel in ascolto su %s", url)
    log.info("OBS → Visualizza → Docks → Custom Browser Docks → URL = %s", url)
    log.info("Profilo Marcato: %s?profile=marcato", url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("shutdown")
        httpd.server_close()


if __name__ == "__main__":
    main()
