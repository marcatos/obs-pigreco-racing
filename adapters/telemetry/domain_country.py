"""Resolve driver nationality for broadcast flags (no IO besides optional JSON)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("pigreco.telemetry.country")

_ROOT = Path(__file__).resolve().parent
_DEFAULT_OVERRIDES = _ROOT / "country_overrides.json"

# iRacing club labels → ISO (best-effort; many clubs are regions).
CLUB_TO_ISO: dict[str, tuple[str, str]] = {
    "italy": ("IT", "Italy"),
    "italia": ("IT", "Italy"),
    "brazil": ("BR", "Brazil"),
    "brasil": ("BR", "Brazil"),
    "spain": ("ES", "Spain"),
    "iberia": ("ES", "Spain"),
    "portugal": ("PT", "Portugal"),
    "france": ("FR", "France"),
    "germany": ("DE", "Germany"),
    "de-at-ch": ("DE", "Germany"),
    "united kingdom": ("GB", "United Kingdom"),
    "uk": ("GB", "United Kingdom"),
    "england": ("GB", "United Kingdom"),
    "netherlands": ("NL", "Netherlands"),
    "holland": ("NL", "Netherlands"),
    "benelux": ("NL", "Netherlands"),
    "belgium": ("BE", "Belgium"),
    "poland": ("PL", "Poland"),
    "australia": ("AU", "Australia"),
    "canada": ("CA", "Canada"),
    "usa": ("US", "United States"),
    "united states": ("US", "United States"),
    "america": ("US", "United States"),
    "international": ("UN", "International"),
    "hispanic": ("MX", "Mexico"),
    "mexico": ("MX", "Mexico"),
    "costa rica": ("CR", "Costa Rica"),
    "nigeria": ("NG", "Nigeria"),
    "africa": ("ZA", "South Africa"),
    "japan": ("JP", "Japan"),
    "asia": ("JP", "Japan"),
    "finland": ("FI", "Finland"),
    "sweden": ("SE", "Sweden"),
    "norway": ("NO", "Norway"),
    "denmark": ("DK", "Denmark"),
    "switzerland": ("CH", "Switzerland"),
    "austria": ("AT", "Austria"),
    "hungary": ("HU", "Hungary"),
    "czech": ("CZ", "Czechia"),
    "czechia": ("CZ", "Czechia"),
    "ireland": ("IE", "Ireland"),
    "new zealand": ("NZ", "New Zealand"),
    "argentina": ("AR", "Argentina"),
    "chile": ("CL", "Chile"),
    "colombia": ("CO", "Colombia"),
    "russia": ("RU", "Russia"),
    "ukraine": ("UA", "Ukraine"),
    "turkey": ("TR", "Turkey"),
    "greece": ("GR", "Greece"),
    "romania": ("RO", "Romania"),
    "south africa": ("ZA", "South Africa"),
}

COUNTRY_NAME_TO_ISO: dict[str, str] = {
    "italy": "IT",
    "spain": "ES",
    "portugal": "PT",
    "brazil": "BR",
    "netherlands": "NL",
    "united kingdom": "GB",
    "great britain": "GB",
    "england": "GB",
    "poland": "PL",
    "united states": "US",
    "usa": "US",
    "australia": "AU",
    "canada": "CA",
    "costa rica": "CR",
    "nigeria": "NG",
    "france": "FR",
    "germany": "DE",
    "belgium": "BE",
    "mexico": "MX",
    "japan": "JP",
    "argentina": "AR",
    "kazakhstan": "KZ",
    "taiwan": "TW",
    "slovenia": "SI",
    "switzerland": "CH",
    "colombia": "CO",
    "south africa": "ZA",
}


def normalize_driver_name(name: str | None) -> str:
    s = str(name or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _load_overrides(path: Path | None = None) -> dict[str, Any]:
    p = path or _DEFAULT_OVERRIDES
    if not p.is_file():
        return {"byUserId": {}, "byName": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("country overrides load failed path=%s err=%s", p, exc)
        return {"byUserId": {}, "byName": {}}
    if not isinstance(data, dict):
        return {"byUserId": {}, "byName": {}}
    return {
        "byUserId": dict(data.get("byUserId") or {}),
        "byName": dict(data.get("byName") or {}),
    }


_OVERRIDES = _load_overrides()


def reload_overrides(path: Path | None = None) -> None:
    global _OVERRIDES
    _OVERRIDES = _load_overrides(path)


def _entry_code_name(entry: Any) -> tuple[str | None, str | None]:
    if isinstance(entry, str):
        code = entry.strip().upper()
        if len(code) == 2:
            return code, None
        return None, None
    if isinstance(entry, dict):
        code = str(entry.get("code") or entry.get("countryCode") or "").strip().upper()
        name = str(entry.get("name") or entry.get("country") or "").strip() or None
        if len(code) == 2:
            return code, name
        if name:
            mapped = COUNTRY_NAME_TO_ISO.get(normalize_driver_name(name))
            if mapped:
                return mapped, name
    return None, None


def resolve_country(
    *,
    user_id: int | None = None,
    name: str | None = None,
    club_name: str | None = None,
    country: str | None = None,
) -> dict[str, str | None]:
    """Return {countryCode, country} — code is ISO-3166 alpha-2 when known."""
    # Explicit country string from enricher / API
    if country:
        cnorm = normalize_driver_name(country)
        code = COUNTRY_NAME_TO_ISO.get(cnorm)
        if code:
            return {"countryCode": code, "country": country.strip()}
        if len(country.strip()) == 2:
            return {"countryCode": country.strip().upper(), "country": None}

    if user_id is not None:
        raw = _OVERRIDES["byUserId"].get(str(int(user_id)))
        if raw is None:
            raw = _OVERRIDES["byUserId"].get(int(user_id))  # type: ignore[arg-type]
        code, cname = _entry_code_name(raw)
        if code:
            return {"countryCode": code, "country": cname}

    nkey = normalize_driver_name(name)
    if nkey:
        code, cname = _entry_code_name(_OVERRIDES["byName"].get(nkey))
        if code:
            return {"countryCode": code, "country": cname}

    club = normalize_driver_name(club_name)
    if club and club in CLUB_TO_ISO:
        code, cname = CLUB_TO_ISO[club]
        return {"countryCode": code, "country": cname}

    return {"countryCode": None, "country": None}
