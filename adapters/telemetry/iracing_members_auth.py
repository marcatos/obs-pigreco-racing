"""iRacing members-ng legacy cookie auth (sync only; no secrets logged)."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from typing import Any

log = logging.getLogger("pigreco.telemetry.iracing_auth")

AUTH_URL = "https://members-ng.iracing.com/auth"
DEFAULT_UA = "obs-pigreco-racing-track-sync/1.0"


def mask_password(password: str, email: str) -> str:
    """base64(sha256(password + email.strip().lower()))."""
    normalized = email.strip().lower()
    digest = hashlib.sha256(f"{password}{normalized}".encode("utf-8")).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_opener() -> urllib.request.OpenerDirector:
    jar = CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def login_session(email: str, password: str, *, opener: urllib.request.OpenerDirector | None = None) -> urllib.request.OpenerDirector:
    """POST /auth; returns opener with session cookies."""
    op = opener or build_opener()
    body = json.dumps(
        {"email": email.strip(), "password": mask_password(password, email)}
    ).encode("utf-8")
    req = urllib.request.Request(
        AUTH_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_UA,
        },
        method="POST",
    )
    log.info("Authenticating to members-ng (email masked in logs)")
    try:
        with op.open(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        log.error("Auth HTTP %s", exc.code)
        raise
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {}
    if isinstance(payload, dict) and payload.get("authcode") == 0:
        # Some responses use authcode; 0 often means failure
        msg = payload.get("message") or payload.get("error") or "auth failed"
        raise RuntimeError(f"iRacing auth rejected: {msg}")
    log.info("Auth OK")
    return op


def fetch_bytes(opener: urllib.request.OpenerDirector, url: str, *, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(opener: urllib.request.OpenerDirector, url: str, *, max_hops: int = 4) -> Any:
    """GET JSON; follow members-ng `link` indirection."""
    current = url
    for hop in range(max_hops):
        log.debug("GET hop=%d url=%s", hop, current.split("?")[0])
        raw = fetch_bytes(opener, current)
        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict) and "link" in data and len(data) <= 2:
            current = str(data["link"])
            continue
        return data
    raise RuntimeError(f"Too many link redirects for {url}")
