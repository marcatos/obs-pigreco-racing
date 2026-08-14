"""iRacing Data API auth helpers (OAuth password_limited; legacy /auth retired)."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

log = logging.getLogger("pigreco.telemetry.iracing_auth")

AUTH_URL = "https://members-ng.iracing.com/auth"
TOKEN_URL = "https://oauth.iracing.com/oauth2/token"
DEFAULT_UA = "obs-pigreco-racing-track-sync/1.1"


def mask_password(password: str, email: str) -> str:
    """base64(sha256(password + email.strip().lower()))."""
    normalized = email.strip().lower()
    digest = hashlib.sha256(f"{password}{normalized}".encode("utf-8")).digest()
    return base64.b64encode(digest).decode("utf-8")


def mask_secret(secret: str, identifier: str) -> str:
    return mask_password(secret, identifier)


def build_opener() -> urllib.request.OpenerDirector:
    jar = CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


class BearerOpener:
    """Minimal opener that injects Authorization: Bearer on open()."""

    def __init__(self, token: str, base: urllib.request.OpenerDirector | None = None):
        self._token = token
        self._base = base or build_opener()

    def open(self, req: urllib.request.Request | str, timeout: float | None = None):
        if isinstance(req, str):
            req = urllib.request.Request(req)
        req.add_header("Authorization", f"Bearer {self._token}")
        if timeout is None:
            return self._base.open(req)
        return self._base.open(req, timeout=timeout)


def login_session(email: str, password: str, *, opener: urllib.request.OpenerDirector | None = None) -> urllib.request.OpenerDirector:
    """Legacy cookie auth — retired by iRacing (kept for clear error)."""
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
    log.info("Trying legacy members-ng /auth (likely retired)")
    try:
        with op.open(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        log.error("Legacy auth HTTP %s — use OAuth client_id/secret or --source paths-dump", exc.code)
        raise
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {}
    if isinstance(payload, dict) and payload.get("authcode") == 0:
        msg = payload.get("message") or payload.get("error") or "auth failed"
        raise RuntimeError(f"iRacing auth rejected: {msg}")
    log.info("Legacy auth OK")
    return op


def login_password_limited(
    *,
    client_id: str,
    client_secret: str,
    email: str,
    password: str,
) -> BearerOpener:
    """OAuth2 password_limited grant → Bearer opener for Data API."""
    form = {
        "grant_type": "password_limited",
        "client_id": client_id,
        "client_secret": mask_secret(client_secret, client_id),
        "username": email.strip(),
        "password": mask_password(password, email),
        "scope": "iracing.auth",
    }
    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": DEFAULT_UA,
        },
        method="POST",
    )
    log.info("OAuth password_limited token request (secrets not logged)")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("OAuth response missing access_token")
    log.info("OAuth OK expires_in=%s", payload.get("expires_in"))
    return BearerOpener(str(token))


def load_cred_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def login_oauth_or_legacy(cred_path: Path) -> Any:
    import os

    data = load_cred_file(cred_path)
    email = (os.environ.get("IRACING_EMAIL") or str(data.get("email") or "")).strip()
    password = os.environ.get("IRACING_PASSWORD") or str(data.get("password") or "")
    client_id = (
        os.environ.get("IRACING_CLIENT_ID")
        or str(data.get("client_id") or data.get("clientId") or "")
    ).strip()
    client_secret = os.environ.get("IRACING_CLIENT_SECRET") or str(
        data.get("client_secret") or data.get("clientSecret") or ""
    )

    if client_id and client_secret and email and password:
        return login_password_limited(
            client_id=client_id,
            client_secret=client_secret,
            email=email,
            password=password,
        )
    if email and password:
        log.warning(
            "No client_id/client_secret — legacy /auth is retired. "
            "Prefer --source paths-dump, or add OAuth credentials when iRacing reopens registration."
        )
        return login_session(email, password)
    raise SystemExit(
        "Missing credentials for --source api. Need email/password + client_id/client_secret "
        "in iracing_api.local.json, or use default --source paths-dump."
    )


def fetch_bytes(opener: Any, url: str, *, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(opener: Any, url: str, *, max_hops: int = 4) -> Any:
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
