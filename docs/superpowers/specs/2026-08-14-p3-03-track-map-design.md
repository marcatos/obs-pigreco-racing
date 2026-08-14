# Design: P3-03 Minimap / track map (hybrid catalog)

**Date:** 2026-08-14  
**Status:** approved (conversation); pending file review  
**Roadmap:** P3-03  
**Related:** ADR-005, `adapters/telemetry/CONTRACT.md`, broadcast chrome layout rules

## Problem

Telecronaca needs a peripheral track map with cars as dots. User wants **pro per-track** maps and a **wide catalog**, without copying proprietary iRacing map art. Source of geometry: **open assets where available** + **self-learn** polyline from the live/replay session.

## Goals

- Browser Source minimap (1920×1080 canvas, corner placement, never center FOV).
- Show field as dots along track path; focus car highlighted (brand / Marcato tokens).
- Resolver order: **open SVG/JSON asset → learned JSON → generic oval fallback**.
- Self-learn in the telemetry adapter: accumulate path samples per track identity; persist locally.
- Additive CONTRACT fields only (`schemaVersion` 1).
- Works with mock server for UI smoke tests.

## Non-goals

- Pixel-perfect official iRacing/ACC track maps.
- Shipping copyrighted game HUD crops.
- Full GPS GIS pipeline.
- Replacing SimHub as optional third-party (docs may still mention it).

## Architecture

```
Bridge / mock
  → telemetry.tick (+ mapCars, trackId)
       → overlays/track-map.js
            → resolveTrackAsset(trackId|trackName)
                 1. overlays/assets/tracks/open/{id}.svg|json
                 2. learned/{id}.json  (local)
                 3. generic fallback path
            → place dots by distPct along path length
```

Self-learn (adapter):

```
Each tick with valid focus motion
  → sample (distPct, x, y) into ring buffer for trackId
  → on lap complete / session end / periodic flush
  → write learned JSON (gitignored)
```

Coordinate basis for learn: prefer iRacing velocity/yaw integration or available world coords when present; store normalized 0–1 viewBox-friendly polyline keyed by `distPct`. Exact numeric source documented in implementation plan after SDK probe — design locks **distPct → point on path** as the overlay contract.

## CONTRACT extensions (additive)

On `telemetry.tick`:

| Field | Type | Notes |
|-------|------|-------|
| `trackId` | string \| null | Stable id when known (weekend / config string) |
| `mapCars` | array | See below |

**`mapCars[]`**

| Field | Type |
|-------|------|
| `carIdx` | number |
| `carNumber` | string |
| `distPct` | number (0–1) |
| `isFocus` | boolean |

Consumers ignore unknown fields. Full standings remain separate.

## Overlay

- New `overlays/track-map.html` (+ shared CSS module); Marcato can reuse via relative scripts/theme.
- Config: `trackMapEnabled` (default false), `trackMapWsUrl` (default telemetry URL), optional size/corner.
- OBS: Browser Source HTTP URL via config server (`/o/.../track-map.html`), eye off by default.
- Layout: bottom-right (or config), ~280–360 px, transparent stage, no center coverage.

## Track asset layout

```
overlays/assets/tracks/
  open/           # optional curated open SVGs / path JSON (in repo)
  README.md       # how to add an open asset; naming = trackId
adapters/telemetry/tracks_learned/   # gitignored learned JSON
```

Open pack: start with whatever redistributable outlines we can place; “wide catalog” grows via learn + occasional open additions — not a promise of every iRacing track on day one.

## Files

| Path | Role |
|------|------|
| `adapters/telemetry/` learn + `mapCars` fill | Bridge / mock |
| `adapters/telemetry/domain_track_map.py` | Pure distPct→point / simplify helpers |
| `overlays/track-map.*` | UI |
| `overlays/assets/tracks/` | Open assets + README |
| `docs/TRACK_MAP.md` | Operator + learn instructions |
| `tests/test_track_map.py` | Path math + resolver |
| `docs/ROADMAP.md` | P3-03 |

## Acceptance

- Mock: cars move along fallback or sample open path; focus distinct.
- After one learned lap on a track, reload overlay uses learned outline without open asset.
- Missing asset → generic fallback, no blank crash.
- `trackMapEnabled: false` → no WS / hidden.
- Unit tests without SDK for path sampling math.

## Risks

| Risk | Mitigation |
|------|------------|
| Ugly first-lap learn | Simplify/smooth polyline; require min samples |
| trackId mismatch open vs learn | Normalize names; alias map in JSON |
| Replay scrub jumps | Reset learn buffer on large sessionTime rewind (reuse continuity helpers) |
| FOV / clutter | Corner only; default off |
