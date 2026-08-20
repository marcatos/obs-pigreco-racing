# Design — Session reset (telemetry + director + overlays)

**Date:** 2026-08-20  
**Status:** approved (pending implement)  
**Plane:** [OBSPI-60](https://plane.marcatos.ddns.net) — feat: session reset (auto + VirtualDeck)  

**Related:** [`SESSION_DIRECTOR.md`](../../SESSION_DIRECTOR.md), [`adapters/telemetry/CONTRACT.md`](../../../adapters/telemetry/CONTRACT.md), [`2026-08-14-marcato-session-director-design.md`](2026-08-14-marcato-session-director-design.md)

## Goal

Allow recording / streaming **multiple iRacing races without restarting** Session Director or the telemetry bridge. Clear stale overlay standings, hero moments, and event memory when a new session starts — automatically — with a VirtualDeck emergency button for the same path.

## Problem

Today continuity resets mainly on **sim disconnect** and camera/session-time jumps. Staying in iRacing across races can leave:

- Overlay hero queue / fight pack / standings freeze from the previous race
- Event detector debounce / streaks
- Instant-replay cooldown and sticky flag state in the director

Operators currently restart processes to get a clean slate.

## Decision

**Approach A — single `session_reset` bus**, shared by auto-detect and manual VirtualDeck.

Do **not** kill/restart Python processes for normal race changes.

## Architecture

```text
iRacing SDK                         VirtualDeck
   │  session key                      │  scene "Reset Session"
   ▼                                   ▼
Telemetry bridge ◄── telemetry.command ── Session Director
   │                      session_reset
   │  WS: telemetry.session_reset
   ├──────────────► Broadcast overlays
   └──────────────► Director (echo: replay cooldown / sticky flag)
```

One internal reset path; two entry points (auto key change, manual scene).

## Session key (auto)

Prefer, in order:

1. iRacing `SessionUniqueID` when present
2. Else `(weekend/track id, SessionNum, session kind)`

Rules:

- On **first** latch after connect: store key, **do not** emit reset
- On **key change**: `reset_continuity()` (detector, pos/dist maps, grid latch, open sectors) then broadcast `telemetry.session_reset`
- Debounce resets (~1–2 s) so auto + manual do not double-fire
- Missing/unstable key: do not thrash; log WARN once and skip until a stable key appears
- Existing disconnect path may emit `reason: sim_disconnected`; reconnect latches a new key without a spurious extra reset if the key is unchanged

## WS contract (additive, schemaVersion 1)

```json
{
  "type": "telemetry.session_reset",
  "schemaVersion": 1,
  "ts": 1738000000123,
  "reason": "session_changed",
  "sessionKey": "abc123",
  "previousKey": "xyz789"
}
```

| Field | Type | Notes |
|-------|------|--------|
| `reason` | string | `session_changed` \| `manual` \| `sim_disconnected` |
| `sessionKey` | string \| null | New key after reset (null if disconnected) |
| `previousKey` | string \| null | Optional prior key |

Consumers must ignore unknown fields. Document in `adapters/telemetry/CONTRACT.md`.

### Manual command (client → bridge)

Session Director is a telemetry WS **client**. For VirtualDeck reset it sends:

```json
{
  "type": "telemetry.command",
  "schemaVersion": 1,
  "ts": 1738000000123,
  "command": "session_reset",
  "reason": "manual"
}
```

The bridge runs the same reset path and **broadcasts** `telemetry.session_reset` to all clients (overlays + director). No second HTTP port. Unknown commands → error frame or log + ignore (do not disconnect).

## What resets

| Layer | Cleared |
|-------|---------|
| Telemetry bridge | Event detector state, pos/dist maps, grid start map, open sector splits (`reset_continuity` + session-key path) |
| Overlays | Hero + queue, moment layer, standings freeze, fight pack; brief status `SESSION RESET` then LIVE on next tick |
| Session Director | Instant-replay policy cooldown / hide clip if showing; clear sticky last-flag used only for change detection |

## What does **not** reset

- OBS scene if operator is on Starting Soon / BRB / Ending (no yank to Live)
- Config / dryRun / OBS password
- OBS Replay Buffer contents (software trigger state only)
- Process lifetime of director / telemetry

## Manual VirtualDeck path

1. Add OBS scene **`Reset Session`** to Marcato pack (`generate_pack.py --profile marcato`) — aux, not part of show flow graphics.
2. Deck checklist button: `SetCurrentProgramScene` → `Reset Session` (`adapters/streamdeck/marcato-live-deck.json`).
3. Session Director on program scene change to `Reset Session`:
   - Send `telemetry.command` / `session_reset` to the bridge (bridge broadcasts `telemetry.session_reset`)
   - Apply local director clear immediately (replay cooldown / hide clip) even before the echo
   - If previous scene was a **race** scene (`Live` / `Headcam`): restore it immediately
   - If previous scene was Starting Soon / BRB / Ending: **stay** there after reset (state only)
4. Treat `Reset Session` like a manual/aux scene so Live↔Lobby automation does not fight it.

Docs: `docs/OBS_VIRTUALDECK.md`, `docs/SESSION_DIRECTOR.md`.

## Overlay behavior

On `telemetry.session_reset` and on `telemetry.status` with `connected: false`:

- Clear director hero/queue and moment UI
- Clear fight / freeze timers
- Do **not** reload the Browser Source

## Error handling

| Case | Behavior |
|------|----------|
| OBS cannot leave `Reset Session` | Log ERROR; software reset still applied |
| Bridge not connected for manual | Director clears local state only; overlays stay until bridge is back (then status/ticks); log WARN |
| Rapid key flicker | Debounce window collapses to one reset |
| Showcase / file fixture mode | Ignore or no-op reset unless fixture includes the message |

## Testing

- Unit: first key latch → no emit; key change → exactly one `session_reset`
- Unit: `telemetry.command` / `session_reset` → broadcast + continuity clear
- Unit: continuity / detector empty after session-change reset
- Unit: director instant-replay `reset()`; `Reset Session` → restore Live when coming from Live
- Unit / light overlay test: reset clears hero queue / freeze
- Docs + CONTRACT + deck JSON updated

## Out of scope

- Killing/restarting telemetry or director processes
- Clearing OBS Replay Buffer disk clips
- Cloud sync or multi-PC reset
- PiGreco Racing pack changes beyond shared telemetry contract (Marcato is primary consumer)

## Acceptance

1. Enter a second race without quitting apps → overlays do not keep previous race standings/hero moments after the session key changes.
2. VirtualDeck **Reset Session** produces the same clean UI without restarting Python/OBS.
3. Starting Soon / BRB / Ending are not auto-left by reset.
4. `pytest` covers session-key and director restore paths; CONTRACT documents the new message.
