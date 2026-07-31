# Telemetry adapter contract

Local bridge between a sim (or mock) and PiGreco Browser Source overlays.

Canonical decision: [`docs/adr/005-telemetry-adapter-port.md`](../../docs/adr/005-telemetry-adapter-port.md).

## Transport

| Mode | Endpoint | Notes |
|------|----------|-------|
| **WebSocket (preferred)** | `ws://127.0.0.1:8765` | JSON text frames, one object per message |
| **File fallback** | `adapters/telemetry/telemetry.json` | Latest `telemetry.tick` overwritten each tick |

Default bind: `127.0.0.1` only (not LAN). Change host/port via mock CLI flags when needed.

## Schema version

`schemaVersion: 1` on every message. Consumers must ignore unknown fields and reject unsupported major versions only when they cannot parse required fields.

## Envelope

```json
{
  "type": "<message-type>",
  "schemaVersion": 1,
  "ts": 1738000000123
}
```

`ts` is Unix epoch milliseconds (UTC).

## Message types

### `telemetry.hello` (server → client)

Sent once after WebSocket accept.

```json
{
  "type": "telemetry.hello",
  "schemaVersion": 1,
  "ts": 1738000000000,
  "server": "pigreco-telemetry-mock",
  "tickHz": 10,
  "modes": ["websocket"]
}
```

### `telemetry.tick` (server → client)

Periodic snapshot. Fields:

| Field | Type | Description |
|-------|------|-------------|
| `session` | string | `practice` \| `quali` \| `race` \| `cooldown` \| `unknown` |
| `sessionTimeMs` | number \| null | Elapsed session time (ms) |
| `position` | number \| null | 1-based place |
| `positionOf` | number \| null | Field size |
| `gapAheadMs` | number \| null | Gap to car ahead (ms); `0` if leading |
| `gapBehindMs` | number \| null | Gap to car behind (ms) |
| `lastLapMs` | number \| null | Last completed lap |
| `bestLapMs` | number \| null | Best lap this session |
| `currentLapMs` | number \| null | Ongoing lap time |
| `lap` | number \| null | Current lap |
| `lapsTotal` | number \| null | Scheduled laps; null if timed |
| `flag` | string | `none` \| `green` \| `yellow` \| `blue` \| `white` \| `checkered` \| `red` \| `black` \| `meatball` |
| `trackName` | string \| null | Track name |
| `carName` | string \| null | Car name |
| `speedKph` | number \| null | Speed km/h |
| `gear` | number \| null | Gear (`-1` R, `0` N) |
| `rpm` | number \| null | RPM |
| `fuelPct` | number \| null | Fuel 0–100 |
| `connected` | boolean | Bridge sees a live session |

### `telemetry.status` (server → client)

Bridge / sim health (e.g. disconnect).

```json
{
  "type": "telemetry.status",
  "schemaVersion": 1,
  "ts": 1738000000500,
  "connected": false,
  "reason": "sim_disconnected"
}
```

### `client.ping` / `server.pong`

Optional keepalive. Client may send `{"type":"client.ping","schemaVersion":1,"ts":…}`; server replies `server.pong` with same `ts` echoed in `pingTs` when present.

## Overlay rules

1. Read only this contract — never call a sim SDK from Browser Source JS.
2. Gate UI with `telemetryEnabled` (default `false`) in `overlays/config.js`.
3. Optional URL override: `telemetryWsUrl` (default `ws://127.0.0.1:8765`).
4. Stay off the center gameplay zone (design system / live chrome margins).

## Run the mock

From repo root:

```powershell
# Preferred: WebSocket producer (requires: pip install websockets)
python adapters/telemetry/mock_server.py

# File-only fallback (stdlib only — writes telemetry.json)
python adapters/telemetry/mock_server.py --mode file

# Both WebSocket + file mirror
python adapters/telemetry/mock_server.py --mode both

# Debug logging
python adapters/telemetry/mock_server.py --log-level DEBUG
```

Dependency: **`websockets`** for `--mode ws` / `both`. Install with:

```powershell
pip install websockets
```

`--mode file` needs no extra packages.

## Future adapters

Real bridges (SimHub plugin, iRacing SDK, …) must emit the same message types and field names. Do not extend overlays until the adapter speaks this contract.
