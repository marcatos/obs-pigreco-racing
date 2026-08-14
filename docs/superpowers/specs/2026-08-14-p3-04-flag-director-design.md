# Design: P3-04 Auto scene on flags (OBS + overlay)

**Date:** 2026-08-14  
**Status:** approved
**Roadmap:** P3-04  
**Related:** ADR-005, P3-06 `telemetry.event` / `flag`, `docs/TELEMETRY_BROADCAST.md`

## Problem

On yellow / red / checkered the stream should react beyond the broadcast chrome banner: OBS should switch to dedicated flag scenes, then return to the live/race scene when green returns. Overlay flag UX already exists and must stay on.

## Goals

- Switch OBS scenes via **obs-websocket v5** on `yellow` | `red` | `checkered`.
- **Auto-return** to the previous non-flag (“home”) scene on `green` (and treat quiet `none` like green when already racing).
- Keep broadcast overlay flag banner / director chips independent (always available when telemetry is on).
- Optional local process; core pack still works without it.
- No secrets in git (OBS websocket password via local env / gitignored config).

## Non-goals

- Auto-director for iRacing cameras (camera car / replay cams).
- Switching on blue / white / black / meatball in v1 (configurable later; white may optionally map to finish scene).
- Embedding OBS control inside Browser Source JS.
- Replacing P3-06 moment layer.

## Architecture

```
iRacing / mock → telemetry WS :8765
                      ↓
            adapters/obs_flag_director/
                      ↓ obs-websocket :4455
                    OBS scenes
                      
Same ticks/events → overlays/broadcast.js (unchanged path)
```

**Boundary:** dedicated adapter process (Approach A). Does not live inside `iracing_bridge.py`.

## Behavior

| Flag | Action |
|------|--------|
| `yellow` | Switch to configured caution scene |
| `red` | Switch to configured red scene |
| `checkered` | Switch to configured finish/checkered scene |
| `green` | Return to **home** (last non-flag scene, or configured default live scene) |
| other | No scene change in v1 (overlay may still show) |

**Home stack:** when leaving a non-flag scene for a flag scene, remember `previousSceneName`. On green, restore it. If unknown, use `flagDirectorHomeScene` from config.

**Debounce:** ignore flag flaps shorter than ~1.5–2 s. Skip OBS call if already on target scene.

**Source of truth for flag:** prefer `telemetry.event` `flag_change`; also latch from `telemetry.tick.flag` so late connect still works (same idea as banner latch).

## Config (local)

Example `adapters/obs_flag_director/config.example.json` (copy to gitignored `config.local.json`):

```json
{
  "telemetryWsUrl": "ws://127.0.0.1:8765",
  "obsHost": "127.0.0.1",
  "obsPort": 4455,
  "obsPassword": "",
  "enabled": true,
  "debounceMs": 1500,
  "homeScene": "Rec * Live",
  "scenes": {
    "yellow": "Flag Yellow",
    "red": "Flag Red",
    "checkered": "Flag Checkered"
  }
}
```

Scene names must match OBS collection (Marcato / PiGreco / Rec 2K — document per pack). Pack generator may add empty placeholder scenes later; v1 can document “create these scenes once”.

## Files

| Path | Role |
|------|------|
| `adapters/obs_flag_director/` | Domain mapping + OBS + telemetry clients |
| `adapters/obs_flag_director/config.example.json` | Template |
| `Start-FlagDirector.bat` | CRLF launcher |
| `docs/FLAG_DIRECTOR.md` | Operator setup (OBS websocket, scene names) |
| `tests/test_flag_director.py` | Pure mapping / debounce tests |
| `docs/ROADMAP.md` | P3-04 → done when shipped |

## Dependencies

- `obsws-python` or equivalent obs-websocket v5 client (pin in `requirements.txt` under adapter folder).
- Existing `websockets` for telemetry client.

## Acceptance

- Mock: scripted yellow → director requests scene `Flag Yellow`; green → home.
- With OBS + websocket enabled: real scene switch; overlay still shows yellow banner.
- `enabled: false` or missing password: process logs and no-ops without crashing.
- Unit tests without live OBS.

## Risks

| Risk | Mitigation |
|------|------------|
| Wrong scene names | Example config + docs; dry-run log mode |
| Fight with manual scene changes | Only act on flag edges; short debounce |
| Password leak | gitignore `config.local.json`; never log password |
