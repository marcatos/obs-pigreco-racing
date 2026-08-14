# Design: Official iRacing SVG track maps (P3-07)

**Date:** 2026-08-14  
**Status:** pending-review  
**Roadmap:** P3-07 (supersedes geometry source for P3-03)  
**Related:** ADR-005, `adapters/telemetry/CONTRACT.md`, `docs/TRACK_MAP.md`, prior `2026-08-14-p3-03-track-map-design.md`

## Problem

The current minimap uses open JSON / self-learned polylines / a generic oval. That looks amateur on stream. Official iRacing track map SVG layers (Data API track assets) are the correct geometry. Local install `tracks\*.dat` packs are proprietary binaries and are **not** usable as map art.

## Goals

- One-shot / occasional **local sync** of iRacing track SVG assets keyed by numeric **`TrackID`**.
- Overlay renders those SVGs (stroke styled to brand) and places `mapCars` by `distPct` along the main track path.
- Bridge emits raw numeric `TrackID` as `trackId` (string form of the integer, e.g. `"449"`).
- Cache stays on the pilot PC; **not** shipped in public pack zip / git.
- Operator path: BAT + env/local secrets; no secrets in git.
- Missing cache → clear operator hint (sync needed), **not** oval fallback as primary UX.

## Non-goals

- Runtime iRacing login during a race (no sync inside hot path of `iracing_bridge`).
- Reverse-engineering `Program Files (x86)\iRacing\tracks\**\*.dat`.
- Committing or redistributing iRacing SVG art in the public repo/release.
- Keeping open/self-learn as the primary geometry source (retire from happy path).
- Perfect S/F offset calibration for every track on day one (optional per-track meta later).

## Chosen approach

**Approach 1 — Python one-shot sync CLI** (approved):

```
Start-SyncTrackMaps.bat
  → adapters/telemetry/sync_iracing_track_maps.py
       auth (legacy members hash or documented OAuth)
       GET /data/track/assets (+ follow links / download SVG layers)
  → overlays/assets/tracks/iracing/{trackId}.svg
  → overlays/assets/tracks/iracing/{trackId}.meta.json  (optional offset/direction)
  → gitignored
```

Rejected alternatives (same epic): runtime sync in bridge; Node `@iracing-data/sync-track-assets` as required Setup dependency.

## Architecture

```
[Operator PC]
  sync_iracing_track_maps.py  --once / --force
        ↓ writes
  overlays/assets/tracks/iracing/{TrackID}.svg   (gitignored)

[Race day]
  iracing_bridge → telemetry.tick.trackId = "449"
                 → mapCars[] with distPct
        ↓ WS
  broadcast-chrome / track-map.js
        → fetch assets/tracks/iracing/449.svg (via config server)
        → paint path + dots
```

**Boundaries**

| Layer | Responsibility |
|-------|----------------|
| Domain | Path length / `distPct` → point; optional offset/direction normalize |
| Application | Resolve track asset path by TrackID; decide missing vs ready |
| Adapters | Sync CLI (HTTP + auth + FS write); overlay fetch/render; bridge field fill |
| Ports | “Track SVG store” (read by TrackID); “iRacing track assets API” (sync only) |

## CONTRACT

Keep `mapCars[]` as today.

Change `trackId` semantics:

| Field | Was | Becomes |
|-------|-----|---------|
| `trackId` | Slug from name (`monza-gp`) when TrackID missing | Prefer **stringified WeekendInfo.TrackID** (`"449"`). Fallback slug only if SDK has no TrackID (mock may use a fixture id). |

Add optional tick field (additive, ignore if absent):

| Field | Type | Notes |
|-------|------|-------|
| `trackConfig` | string \| null | Layout name if useful for multi-config assets later |

Mock: pin a known fixture TrackID that ships a **tiny synthetic SVG under `tests/fixtures/`** (not real iRacing art) so CI does not need credentials.

## Overlay behavior

- Prefer SVG under `assets/tracks/iracing/{trackId}.svg` (and Marcato relative `../overlays/assets/...`).
- Style: brand stroke (`#00C400` / Marcato accent), dark fill panel, mid-right (clear of Cam 2).
- Place cars by arc-length along the primary path element(s); focus larger / brighter.
- If SVG missing: show compact status `"TRACK MAP — run Start-SyncTrackMaps"`; do not draw oval as default.
- Optional `meta.json`: `{ "offset": 0.0, "direction": 1 }` for S/F alignment (default identity).
- Remains embedded in Broadcast Chrome when `trackMapEnabled`; standalone `track-map.html` still works.

## Auth & secrets

- Credentials via env and/or gitignored `adapters/telemetry/iracing_api.local.json` (example committed without secrets).
- Never log password / token values.
- Sync is offline-of-race: operator runs when adding tracks / after seasons.

Exact auth method (legacy password hash vs OAuth client) is an implementation detail locked in the plan after a short spike; design requires **local-only secrets** and **no cloud dependency for core pack at stream time**.

## Retire / demote

| Current | After P3-07 |
|---------|-------------|
| `overlays/assets/tracks/open/` as primary | Optional leftover; not required |
| `track_learn.py` / learned/ | Disabled by default or removed from bridge path |
| Generic oval | Dev-only / tests only |

## Files (expected)

| Path | Role |
|------|------|
| `adapters/telemetry/sync_iracing_track_maps.py` | Sync CLI |
| `Start-SyncTrackMaps.bat` | Operator entry |
| `overlays/assets/tracks/iracing/` | Cache (gitignored) + `.gitkeep` or README only |
| `overlays/track-map.js` + CSS | SVG render + missing state |
| `adapters/telemetry/iracing_bridge.py` | Emit numeric TrackID |
| `docs/TRACK_MAP.md` | Operator sync steps |
| `tests/test_track_map_svg.py` (+ fixture SVG) | Path math / resolver without live API |
| `.gitignore` | `overlays/assets/tracks/iracing/*.svg`, `*.meta.json`, api local secrets |
| `docs/ROADMAP.md` | P3-07 |

## Acceptance

- After sync for a TrackID present in session, minimap shows official outline (not oval/learned scribble).
- `trackId` on tick matches SDK TrackID string for live/replay.
- Without cache: visible sync hint; overlay does not crash.
- Mock/CI: fixture SVG path works with no iRacing credentials.
- No iRacing credentials or SVG blobs committed.
- Docs: sync BAT + enable checklist updated.

## Risks

| Risk | Mitigation |
|------|------------|
| API / ToS / auth churn | Isolate auth in one adapter; document failure modes |
| SVG redistrib | gitignore + docs “personal use / local cache” |
| Path vs LapDistPct misaligned | optional per-track offset/direction meta |
| Multi-layout TrackID | prefer assets matching active config when API exposes them; else primary map |
| Large catalog download | sync supports `--track-id` filter + resume/skip existing |

## Supersession note

`docs/superpowers/specs/2026-08-14-p3-03-track-map-design.md` remains historical for the first ship. **Geometry source of truth for new work is this document (P3-07).** Overlay placement and CONTRACT `mapCars` from P3-03 stay.
