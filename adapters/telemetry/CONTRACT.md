# Telemetry adapter contract

Local bridge between a sim (or mock) and PiGreco / S.Marcato Browser Source overlays.

Canonical decision: [`docs/adr/005-telemetry-adapter-port.md`](../../docs/adr/005-telemetry-adapter-port.md).

## Transport

| Mode | Endpoint | Notes |
|------|----------|-------|
| **WebSocket (preferred)** | `ws://127.0.0.1:8765` | JSON text frames, one object per message |
| **File fallback** | `adapters/telemetry/telemetry.json` | Latest `telemetry.tick` overwritten each tick |

Default bind: `127.0.0.1` only (not LAN). Change host/port via CLI flags when needed.

## Schema version

`schemaVersion: 1` on every message. Consumers must ignore **unknown / optional** fields and keep working. Optional broadcast fields below are additive (P3-02 telecronaca).

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

Periodic snapshot.

#### Core fields (P3-01)

| Field | Type | Description |
|-------|------|-------------|
| `session` | string | `practice` \| `quali` \| `race` \| `cooldown` \| `unknown` |
| `sessionTimeMs` | number \| null | Elapsed session time (ms) |
| `position` | number \| null | Focus car 1-based place |
| `positionOf` | number \| null | Field size |
| `gapAheadMs` | number \| null | Gap to car ahead (ms); `0` if leading |
| `gapBehindMs` | number \| null | Gap to car behind (ms) |
| `lastLapMs` | number \| null | Last completed lap |
| `bestLapMs` | number \| null | Best lap this session |
| `currentLapMs` | number \| null | Ongoing lap time |
| `lap` | number \| null | Current lap (focus) |
| `lapsTotal` | number \| null | Scheduled laps; null if timed |
| `flag` | string | `none` \| `green` \| `yellow` \| `blue` \| `white` \| `checkered` \| `red` \| `black` \| `meatball` |
| `trackName` | string \| null | Track name |
| `carName` | string \| null | Focus car name |
| `speedKph` | number \| null | Speed km/h |
| `gear` | number \| null | Gear (`-1` R, `0` N) |
| `rpm` | number \| null | RPM |
| `fuelPct` | number \| null | Fuel 0–100 |
| `connected` | boolean | Bridge sees a session |

#### Optional broadcast fields (P3-02 — ignore if absent)

| Field | Type | Description |
|-------|------|-------------|
| `isReplay` | boolean | True when source is an iRacing replay (or mock replay mode) |
| `focusCarIdx` | number \| null | SDK car index in camera / focus |
| `focusDriverName` | string \| null | Driver display name |
| `focusCarNumber` | string \| null | Car number string |
| `focusClassPosition` | number \| null | Class position when available |
| `sessionLapsRemain` | number \| null | Laps remaining |
| `sessionTimeRemainMs` | number \| null | Session time remaining |
| `standings` | array | Leaderboard rows (see below) |
| `relatives` | array | Short ahead/behind list around focus |

**`standings[]` row**

| Field | Type | Description |
|-------|------|-------------|
| `pos` | number | 1-based overall (or class) position |
| `carNumber` | string | Race number |
| `name` | string | Driver / short name |
| `gapMs` | number \| null | Gap to leader (ms); `0` for P1 |
| `intervalMs` | number \| null | Gap to car ahead (ms) |
| `lastLapMs` | number \| null | Last lap |
| `bestLapMs` | number \| null | Best lap |
| `class` | string \| null | Class name |
| `carIdx` | number \| null | SDK index |
| `isFocus` | boolean | Row is camera focus |

**`relatives[]` row**

| Field | Type | Description |
|-------|------|-------------|
| `rel` | number | Negative = ahead, `0` = focus, positive = behind |
| `carNumber` | string | |
| `name` | string | |
| `gapMs` | number \| null | Interval to focus (ms), signed by `rel` |
| `carIdx` | number \| null | |

### `telemetry.status` (server → client)

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

Optional keepalive.

## Overlay rules

1. Read only this contract — never call a sim SDK from Browser Source JS.
2. Gate UI with `telemetryEnabled` (default `false`) in config.
3. Optional URL override: `telemetryWsUrl` (default `ws://127.0.0.1:8765`).
4. Stay off the center gameplay zone (design system / live chrome margins).
5. Prefer a single `broadcast-chrome.html` Browser Source over many small ones.

## Run producers

```powershell
# Mock (UI development)
python adapters/telemetry/mock_server.py

# iRacing bridge (replay or live — iRacing must be open)
python adapters/telemetry/iracing_bridge.py
```

Dependency: **`websockets`**. iRacing bridge also needs **`pyirsdk`** when talking to the sim.

```powershell
pip install websockets pyirsdk
```

`--mode file` on the mock needs no extra packages.

## Future adapters

Real bridges must emit the same message types and field names. Optional fields may be omitted.
