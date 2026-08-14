# P3-07 Official iRacing SVG Track Maps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace open/self-learn/oval minimap geometry with locally cached official iRacing track SVG assets keyed by numeric TrackID.

**Architecture:** One-shot Python sync CLI authenticates to members-ng, downloads track SVG layers into a gitignored cache. Bridge emits stringified `TrackID`. Overlay fetches `{trackId}.svg`, styles the path, places `mapCars` by arc-length `distPct` (+ optional meta offset/direction). Missing cache shows an operator hint — no oval happy path.

**Tech Stack:** Python 3 stdlib (`urllib`/`hashlib`/`json`) + existing pytest; HTML/CSS/JS overlay; no new runtime deps for race day.

## Global Constraints

- Canvas **1920×1080**; map mid-right; never center FOV.
- Brand stroke `#00C400` (Marcato accent via CSS var).
- **No** iRacing SVG blobs or API credentials in git / public zip.
- `schemaVersion` stays **1**; additive fields only.
- Claim ROADMAP **P3-07**.
- Spec: `docs/superpowers/specs/2026-08-14-iracing-svg-track-maps-design.md`.
- Auth: legacy members-ng cookie login (email + SHA256-masked password). No OAuth client registration required for v1.
- Sync is offline-of-race only (never inside `iracing_bridge` hot path).

## File map

| Path | Responsibility |
|------|----------------|
| `adapters/telemetry/domain_track_map.py` | Add `format_track_id`, `apply_dist_offset` |
| `adapters/telemetry/iracing_members_auth.py` | Mask + login + authenticated GET helpers |
| `adapters/telemetry/sync_iracing_track_maps.py` | CLI: fetch assets, write SVG+meta |
| `adapters/telemetry/iracing_api.example.json` | Credential template (no secrets) |
| `Start-SyncTrackMaps.bat` | Operator entry |
| `overlays/assets/tracks/iracing/README.md` | Cache explanation + `.gitkeep` |
| `overlays/track-map.js` | SVG load + path getPointAtLength + missing hint |
| `overlays/assets/broadcast-map.css` | Hint + SVG host styles |
| `overlays/track-map.html` + broadcast chrome | Host for track SVG group |
| `adapters/telemetry/iracing_bridge.py` | Emit numeric TrackID; disable learn by default |
| `adapters/telemetry/mock_server.py` | Fixture TrackID `900001` |
| `tests/fixtures/tracks/900001.svg` | Tiny synthetic SVG (not iRacing art) |
| `tests/test_track_map_svg.py` | Domain + resolve helpers |
| `docs/TRACK_MAP.md`, `CONTRACT.md`, `ROADMAP.md` | Ops + claim done |
| `.gitignore` | iracing cache + `iracing_api.local.json` |

---

### Task 1: Domain helpers + tests

**Files:**
- Modify: `adapters/telemetry/domain_track_map.py`
- Modify: `tests/test_track_map.py` (or create `tests/test_track_map_svg.py`)

**Interfaces:**
- Produces: `format_track_id(raw: object | None, fallback_name: str | None = None) -> str`
- Produces: `apply_dist_offset(dist_pct: float, *, offset: float = 0.0, direction: int = 1) -> float`

- [ ] **Step 1: Write failing tests**

```python
from domain_track_map import format_track_id, apply_dist_offset

def test_format_track_id_prefers_numeric():
    assert format_track_id(449, "Monza GP") == "449"
    assert format_track_id("449", None) == "449"

def test_format_track_id_falls_back_to_slug():
    assert format_track_id(None, "Monza GP") == "monza-gp"

def test_apply_dist_offset_wraps():
    assert abs(apply_dist_offset(0.9, offset=0.2, direction=1) - 0.1) < 1e-9
    assert abs(apply_dist_offset(0.1, offset=0.0, direction=-1) - 0.9) < 1e-9
```

- [ ] **Step 2: Run tests — expect FAIL (import/attr missing)**

Run: `python -m pytest tests/test_track_map.py -k "format_track_id or apply_dist_offset" -v`

- [ ] **Step 3: Implement**

```python
def format_track_id(raw: object | None, fallback_name: str | None = None) -> str:
    if raw is not None and str(raw).strip().isdigit():
        return str(int(str(raw).strip()))
    return normalize_track_id(str(raw) if raw not in (None, "") else fallback_name)

def apply_dist_offset(dist_pct: float, *, offset: float = 0.0, direction: int = 1) -> float:
    t = float(dist_pct) % 1.0
    if t < 0:
        t += 1.0
    if int(direction) < 0:
        t = (1.0 - t) % 1.0
    t = (t + float(offset)) % 1.0
    if t < 0:
        t += 1.0
    return t
```

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit** `feat(telemetry): add TrackID format and dist offset helpers`

---

### Task 2: Members auth adapter + sync CLI

**Files:**
- Create: `adapters/telemetry/iracing_members_auth.py`
- Create: `adapters/telemetry/sync_iracing_track_maps.py`
- Create: `adapters/telemetry/iracing_api.example.json`
- Create: `Start-SyncTrackMaps.bat`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `mask_password(password: str, email: str) -> str`
- Produces: `login_session(email: str, password: str) -> urllib cookie jar / opener`
- Produces: `fetch_json(opener, url) -> dict` (follows `link` indirection used by members-ng)
- CLI: `python sync_iracing_track_maps.py [--track-id N] [--force] [--out DIR]`

**Auth (legacy cookie):**

```python
# POST https://members-ng.iracing.com/auth
# body JSON: {"email": email, "password": mask_password(password, email)}
# mask = base64(sha256(password + email.strip().lower()))
```

**Assets flow:**

1. GET `https://members-ng.iracing.com/data/track/assets` → may return `{"link": "..."}`; follow until dict keyed by track id strings.
2. For each track (or `--track-id` filter): read fields commonly named `track_map` / `track_map_layers` / SVG URLs under `images-static.iracing.com` (probe real keys on first successful login; prefer active/default layer SVG).
3. Download SVG bytes; write `out/{trackId}.svg`.
4. Write default meta `{ "offset": 0.0, "direction": 1 }` if missing.
5. Skip existing unless `--force`. Log INFO progress: processed/total, skip/ok/fail, elapsed.

**Credentials load order:** env `IRACING_EMAIL` + `IRACING_PASSWORD` → else `adapters/telemetry/iracing_api.local.json` (`email`, `password`). Never log secrets.

**Example JSON:**

```json
{
  "email": "you@example.com",
  "password": "your-password"
}
```

**BAT:**

```bat
@echo off
cd /d "%~dp0"
python adapters\telemetry\sync_iracing_track_maps.py %*
pause
```

**gitignore add:**

```
adapters/telemetry/iracing_api.local.json
overlays/assets/tracks/iracing/*.svg
overlays/assets/tracks/iracing/*.meta.json
```

- [ ] **Step 1: Unit-test `mask_password` only (no network)**

```python
def test_mask_password_stable():
    from iracing_members_auth import mask_password
    a = mask_password("secret", "User@Example.com")
    b = mask_password("secret", "user@example.com")
    assert a == b and len(a) > 20
```

- [ ] **Step 2: Implement auth + sync CLI with logging (INFO default, `--log-level`)**

- [ ] **Step 3: Manual smoke (operator):** copy example → local.json, run `--track-id 449` (or any owned track), confirm SVG lands under `overlays/assets/tracks/iracing/`.

- [ ] **Step 4: Commit** `feat(telemetry): sync official iRacing track SVGs to local cache`

---

### Task 3: Bridge + mock emit numeric TrackID; retire learn hot path

**Files:**
- Modify: `adapters/telemetry/iracing_bridge.py` (trackId + remove/disable `track_learner` sampling)
- Modify: `adapters/telemetry/mock_server.py` (`trackId="900001"`, optional `trackConfig`)
- Modify: `adapters/telemetry/CONTRACT.md`

```python
trackId=format_track_id(track_id_raw, track_name),
trackConfig=weekend.get("TrackConfigName") or weekend.get("TrackConfig") or None,
```

Disable learn: do not call `track_learner.sample` / `set_track` (keep module file for now; no import required).

Mock fixture id `900001` documents that CI copies or serves `tests/fixtures/tracks/900001.svg`.

- [ ] **Step 1: Update CONTRACT.md trackId semantics**

- [ ] **Step 2: Bridge/mock code + existing tests still pass**

Run: `python -m pytest tests/test_track_map.py tests/test_telemetry_broadcast.py -q`

- [ ] **Step 3: Commit** `feat(telemetry): emit numeric TrackID and drop learn hot path`

---

### Task 4: Overlay SVG renderer + missing hint

**Files:**
- Modify: `overlays/track-map.js`
- Modify: `overlays/assets/broadcast-map.css`
- Modify: `overlays/track-map.html` (structure: host `<g data-tm-track>` + cars layer)
- Ensure broadcast-chrome already embeds map root (from prior fix)
- Create: `overlays/assets/tracks/iracing/README.md`
- Create: `tests/fixtures/tracks/900001.svg` (simple rounded rect path — synthetic)

**Resolver order:**

1. `assets/tracks/iracing/{id}.svg` (+ `../overlays/assets/...` from Marcato)
2. For mock/dev only: allow `../tests/fixtures/tracks/{id}.svg` when served? Prefer config-server mapping OR copy fixture into `overlays/assets/tracks/iracing/900001.svg` as **committed synthetic** under a `fixtures` name — **do not** put real iRacing SVG in repo. Commit synthetic as `overlays/assets/tracks/iracing/README.md` says mock uses copy; for CI browser-less tests, JS path resolution unit is optional — Python tests cover domain.

**JS behavior:**

- On tick `trackId`, `fetch` SVG text; inject into `[data-tm-track]` (sanitize: only allow from local same-origin cache).
- Find first meaningful `path` (or combine paths); use `path.getTotalLength()` / `getPointAtLength(dist * len)`.
- Load optional `{id}.meta.json` for offset/direction; apply `applyDistOffset` in JS (duplicate small helper).
- Missing: set label to `TRACK MAP — run Start-SyncTrackMaps`; clear cars; no oval.
- Initial generic oval code path: delete.

**CSS:** `.tm-hint` muted; `.tm-track-svg path { fill: none; stroke: var(--accent); stroke-width: … }`

- [ ] **Step 1: Implement JS/CSS/HTML**

- [ ] **Step 2: Manual OBS check** after sync + Refresh cache

- [ ] **Step 3: Commit** `feat(overlay): render iRacing SVG track maps on minimap`

---

### Task 5: Docs + ROADMAP done

**Files:**
- Modify: `docs/TRACK_MAP.md` (sync BAT, credentials, TrackID, no learn)
- Modify: `docs/TELEMETRY_BROADCAST.md` if still mentions open/learn
- Modify: `docs/ROADMAP.md` P3-07 → `done`
- Modify: spec status → `approved` / implemented

- [ ] **Step 1: Docs rewrite**

- [ ] **Step 2: Commit** `docs(telemetry): operator guide for iRacing SVG track map sync`

---

## Acceptance check

- [ ] Sync writes `{TrackID}.svg` for filtered id without committing secrets
- [ ] Live/replay tick `trackId` is numeric string when SDK TrackID present
- [ ] Overlay shows official outline when cache hit
- [ ] Cache miss shows sync hint (no oval)
- [ ] pytest green without network/credentials
- [ ] P3-07 marked done

## Spec coverage self-review

| Spec item | Task |
|-----------|------|
| Python one-shot sync | T2 |
| Cache path + gitignore | T2 |
| Numeric TrackID | T1+T3 |
| Overlay SVG + dots | T4 |
| Missing hint | T4 |
| Retire learn/oval happy path | T3+T4 |
| Docs + BAT | T2+T5 |
| No secrets in git | T2 |
| Fixture for CI | T4 (+ mock T3) |
| Optional offset meta | T2 write default + T4 read |
