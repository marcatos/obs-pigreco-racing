# Workstream: Sim pro

**Roadmap IDs:** P3-01 … P3-05  
**Owns (planned):** `adapters/telemetry/`, live widgets in overlays, obs-websocket automation docs.

## First step (mandatory)

Land **ADR-005** contract + mock telemetry producer before any HTML binds to a sim. **Done (P3-01):** see `adapters/telemetry/CONTRACT.md` and `mock_server.py`.

## Tasks

- P3-01 Contract + mock server/file — **done**
- P3-02 Position/gap / telecronaca widget + iRacing bridge — **done** (`docs/TELEMETRY_BROADCAST.md`)
- P3-03 Minimap (later)
- P3-04 Auto scene on flags via obs-websocket
- P3-05 Audio bus / VOD documentation for OBS profile

## Constraints

No SDK calls from Browser Source JS directly. Prefer localhost WebSocket.
