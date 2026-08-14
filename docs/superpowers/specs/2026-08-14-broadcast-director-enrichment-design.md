# Design: Broadcast director + enriched telemetry (hybrid)

**Date:** 2026-08-14  
**Status:** approved  
**Roadmap:** extends P3-02; may claim follow-on IDs under `ws-sim-pro`  
**Related:** ADR-005, `adapters/telemetry/CONTRACT.md`, `docs/TELEMETRY_BROADCAST.md`

## Problem

Telecronaca already shows standings / battle / focus / session from a local WebSocket tick. The user wants:

1. **Richer data** (delta, pit, pos change, fuel, etc.) available in the contract.
2. **Not everything on screen at once** — rare full manual enable for replay/telecronaca.
3. **Hybrid control:** automatic motorsport-style graphic moments from telemetry, plus manual overrides.

## Goals

- Enrich `telemetry.tick` additively (schemaVersion stays **1**).
- Introduce `telemetry.event` for salient race moments detected in the bridge.
- Single OBS Browser Source (`broadcast-chrome.html`) with base layer + moment layer.
- Config: `broadcastDirector: auto | manual | off` + existing widget toggles as permissions/force.
- Brand-safe motion (2–3 intentional animations); no center FOV coverage.
- Works with mock server (synthetic events) and iRacing bridge (replay + live).

## Non-goals (this design)

- Auto-director for iRacing cameras / OBS scene switching (P3-04 later).
- Custom track map (P3-03).
- Writing Motec files ourselves (IBT remains sim-native via `--ibt`).
- Cloud services.

## Architecture

```
iRacing / mock
    → adapters/telemetry/*_bridge
         ├─ telemetry.tick   (enriched snapshot, ~10 Hz)
         └─ telemetry.event  (sparse; on moment detect)
              → overlays/broadcast.js state machine
                   ├─ base layer (session, focus, optional LB/battle)
                   └─ moment layer (banner / chip / row highlight)
```

**Boundaries**

| Layer | Owns |
|-------|------|
| Domain (`domain_standings.py`, new `domain_events.py`) | Pure detection + enrichment helpers; no IO |
| Bridge / mock | SDK or fake data → CONTRACT messages |
| Overlay JS | Render + animation; no SDK |
| Config | Director mode + widget allow-list |

## Contract extensions (additive)

### `telemetry.tick` — new optional fields

**Focus / car**

| Field | Type | Notes |
|-------|------|-------|
| `deltaBestMs` | number \| null | `lastLapMs - bestLapMs` (negative = purple-ish improvement) |
| `focusClassPosition` | already present | keep |
| `iRating` | number \| null | when DriverInfo provides it |
| `inPit` | boolean \| null | focus car |
| `speedKph` / `gear` / `fuelPct` / `rpm` | already in core | surface in UI when allowed |

**Standings row extras**

| Field | Type | Notes |
|-------|------|-------|
| `posChange` | number \| null | −1 / 0 / +1 vs previous tick (or short window) |
| `inPit` | boolean \| null | |
| `iRating` | number \| null | |

**Session**

| Field | Type | Notes |
|-------|------|-------|
| `airTempC` / `trackTempC` | number \| null | if SDK reliable |
| `sof` | number \| null | strength of field if available |

Consumers must ignore unknown fields.

### `telemetry.event` (new)

```json
{
  "type": "telemetry.event",
  "schemaVersion": 1,
  "ts": 1738000000500,
  "eventId": "uuid-or-monotonic",
  "kind": "flag_change",
  "priority": 100,
  "ttlMs": 4000,
  "payload": { }
}
```

| `kind` | Trigger (bridge) | Typical `payload` |
|--------|------------------|-------------------|
| `flag_change` | `flag` differs from previous tick | `{ "flag": "yellow", "prev": "green" }` |
| `battle` | \|gapAhead\| or \|gapBehind\| &lt; threshold (~1200 ms) for N ticks | `{ "gapMs": 800, "withCarNumber": "7" }` |
| `overtake` | focus `position` improves, or relative swap | `{ "fromPos": 5, "toPos": 4 }` |
| `fast_lap` | focus `lastLapMs` ≤ `bestLapMs` (completed lap) | `{ "lapMs": 90123 }` |
| `pit` | focus (or filmed car) enters/leaves pit | `{ "state": "enter"|"exit" }` |
| `session_end` | checkered or white + last lap heuristics | `{ "flag": "checkered" }` |

**Priority (high → low):** `flag_change` (100) > `overtake` (80) > `battle` (60) > `fast_lap` (50) > `pit` (40) > `session_end` (90 when active).

**Debounce:** per-kind 2–4 s; global one “hero” moment at a time; short queue (max 2).

Mock server emits the same kinds on a deterministic schedule for UI smoke tests.

## Overlay behavior

### Layers

1. **Base** — session strip; compact focus; standings / battle only if allowed by config + director policy.
2. **Moment** — full-width flag banner, floating chip (“OVERTAKE”, “FASTEST”, “PIT”), standings row flash.

### Director modes

| Mode | Behavior |
|------|----------|
| `auto` | Widget toggles = **allow-list**. Director shows/hides and plays moments. Base session+focus preferred on. |
| `manual` | Only toggles; ignore `telemetry.event` for hero UI (still can log). |
| `off` | No moment layer; base follows toggles only (same as today’s static layout). |

`telemetryEnabled: false` still means no WebSocket (unchanged).

### Motion (professional, brand tokens)

- Enter: 240–360 ms slide/fade from edge.
- Accent pulse on flag / overtake (brand `--accent`, no purple glow stacks).
- Exit: fade 200 ms.
- Never cover center gameplay safe zone (DESIGN_SYSTEM).

### Sensitivity

`broadcastDirectorSensitivity: calm | normal | hype`

- calm: higher battle threshold, longer debounce  
- normal: defaults above  
- hype: lower thresholds, shorter debounce  

## Config keys (sync `config.example.js` + panel + both `config.values.json`)

```js
broadcastDirector: "auto",           // auto | manual | off
broadcastDirectorSensitivity: "normal",
// existing:
broadcastLeaderboard: true,
broadcastRelative: true,
broadcastFocus: true,
broadcastSession: true,
```

## File plan

| Path | Role |
|------|------|
| `adapters/telemetry/domain_events.py` | Pure event detection from tick deltas |
| `adapters/telemetry/iracing_bridge.py` / `mock_server.py` | Emit events + enriched fields |
| `adapters/telemetry/CONTRACT.md` | Document tick extras + `telemetry.event` |
| `overlays/broadcast.js` | State machine, layers, animations |
| `overlays/assets/broadcast.css` | Moment styles / keyframes |
| `overlays/config*.js` / `config-panel.html` | New keys |
| `tests/test_telemetry_events.py` | Detector unit tests (no SDK) |
| `docs/TELEMETRY_BROADCAST.md` | Operator guide |

## Phased delivery

### E1 — Enrich tick + UI surfaces
- Contract fields + mock/bridge fill  
- Overlay shows delta / posChange / fuel when focus enabled  
- Tests for sanitization and standings extras  

### E2 — Events + director auto
- `domain_events.py` + emit from mock/bridge  
- Overlay state machine + flag / battle / overtake / fast_lap animations  
- Config `broadcastDirector` + sensitivity  
- Mock scripted events for OBS smoke  

### E3 — Pit / session_end polish
- Pit enter/exit, final lap / checkered treatment  
- Marcato token pass, docs, showcase note  

## Risks

| Risk | Mitigation |
|------|------------|
| Noisy director in replay | Defaults `normal`; calm mode; debounce; allow-list |
| False overtakes from dirty positions | Prefer relative/lap-dist path already used for standings |
| OBS CEF animation jank | Prefer transform/opacity; one hero at a time |
| Scope creep into maps/cameras | Explicit non-goals |

## Acceptance

- Mock: scripted `flag_change` + `battle` animate in Browser Source with `broadcastDirector: auto`.
- Manual mode: no hero chips; toggles only.
- `telemetryEnabled: false`: no WS.
- Pack usable without bridge; Rec 2K / Replay unchanged except overlay content.
- Unit tests for event detector without iRacing.

## Open decisions (defaults locked unless revisited)

- Default director mode: **`auto`**
- Battle threshold normal: **1200 ms**
- Hero TTL default: **4000 ms**
