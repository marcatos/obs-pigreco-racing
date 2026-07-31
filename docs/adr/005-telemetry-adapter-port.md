# ADR-005: Telemetry via adapter port

## Status

Accepted — 2026-07-31

## Context

Phase 3 needs iRacing / ACC / SimHub data on stream without coupling Browser Source HTML to one vendor SDK. Overlays must stay zip-friendly and offline-capable for the core pack; telemetry is an optional local bridge.

## Decision

1. Introduce `adapters/telemetry/` as the **only** place that talks to a sim SDK or SimHub plugin.
2. Expose a **localhost contract** that overlays consume:
   - Primary: WebSocket `ws://127.0.0.1:8765`
   - Fallback: JSON file `adapters/telemetry/telemetry.json` (HTTP/file poll)
3. Overlays subscribe to that contract only (see `CONTRACT.md`). No direct sim SDK imports inside `overlays/*.js`.
4. Ship a **mock producer** first (`mock_server.py`). Real SimHub / iRacing adapters land in later roadmap IDs (P3-02+).

### Message envelope

Every WebSocket frame is a JSON object:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | Message kind (see below) |
| `schemaVersion` | number | yes | Currently `1` |
| `ts` | number | yes | Unix epoch milliseconds (UTC) |

### Message types

| `type` | Direction | Purpose |
|--------|-----------|---------|
| `telemetry.hello` | server → client | Sent once after connect; includes `server` metadata |
| `telemetry.tick` | server → client | Periodic snapshot (~10 Hz mock; real bridge may vary) |
| `telemetry.status` | server → client | Bridge health / sim connected / reason |
| `client.ping` | client → server | Optional keepalive |
| `server.pong` | server → client | Reply to `client.ping` |

### `telemetry.tick` payload fields

All times in **milliseconds** unless noted. Null means “unknown / N/A”.

| Field | Type | Description |
|-------|------|-------------|
| `session` | string | `practice` \| `quali` \| `race` \| `cooldown` \| `unknown` |
| `sessionTimeMs` | number \| null | Elapsed session clock |
| `position` | number \| null | Current class/overall position (1-based) |
| `positionOf` | number \| null | Field size |
| `gapAheadMs` | number \| null | Interval to car ahead (ms); `0` if P1 |
| `gapBehindMs` | number \| null | Interval to car behind (ms) |
| `lastLapMs` | number \| null | Last completed lap time |
| `bestLapMs` | number \| null | Best lap this session |
| `currentLapMs` | number \| null | Lap time in progress |
| `lap` | number \| null | Current lap number |
| `lapsTotal` | number \| null | Race lap total; null for timed sessions |
| `flag` | string | `none` \| `green` \| `yellow` \| `blue` \| `white` \| `checkered` \| `red` \| `black` \| `meatball` |
| `trackName` | string \| null | Track display name |
| `carName` | string \| null | Car / class display name |
| `speedKph` | number \| null | Ground speed |
| `gear` | number \| null | Current gear (`-1` reverse, `0` neutral) |
| `rpm` | number \| null | Engine RPM |
| `fuelPct` | number \| null | Fuel remaining 0–100 |
| `connected` | boolean | Sim/session linked to the bridge |

### Example `telemetry.tick`

```json
{
  "type": "telemetry.tick",
  "schemaVersion": 1,
  "ts": 1738000000123,
  "session": "race",
  "sessionTimeMs": 612340,
  "position": 3,
  "positionOf": 20,
  "gapAheadMs": 234,
  "gapBehindMs": 512,
  "lastLapMs": 91234,
  "bestLapMs": 90801,
  "currentLapMs": 45123,
  "lap": 12,
  "lapsTotal": 25,
  "flag": "green",
  "trackName": "Monza GP",
  "carName": "Ferrari 296 GT3",
  "speedKph": 248.5,
  "gear": 5,
  "rpm": 7200,
  "fuelPct": 42.1,
  "connected": true
}
```

### Overlay config

- `telemetryEnabled: false` by default — widgets stay hidden and do not open sockets until enabled.
- Optional: `telemetryWsUrl` (default `ws://127.0.0.1:8765`).

## Consequences

- Core pack remains usable without Python telemetry process.
- HTML never imports iRacing/SimHub SDKs; only the adapter process does.
- Contract changes require bumping `schemaVersion` and updating `CONTRACT.md` + this ADR.
- P3-02+ widgets bind to this schema only.
