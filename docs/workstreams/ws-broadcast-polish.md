# Workstream: Broadcast polish

**Roadmap IDs:** P1-01 … P1-06  
**Owns:** `overlays/starting-soon.html`, `brb.html`, `ending.html`, `live-chrome.html`, related JS/CSS, maybe `generate_pack.py` for new sources (cam2, media).

## Goals

Make interstitials and live chrome feel “broadcast-ready” without cluttering FOV.

## Ready tasks

### P1-01 Countdown
- Config: `goLiveAt` (ISO local) **or** `countdownSeconds`.
- Show mm:ss on Starting Soon; hide at 0.
- Accept: visible in showcase; config.example updated.

### P1-02 Session badge
- Config: `sessionType`: `practice|quali|race|cooldown|custom` + optional label.
- Small pill top-left stack under/near sponsors or top-center — follow DESIGN_SYSTEM zones.
- Accept: changes with config; doesn’t collide with sponsor rotator (offset).

### P1-03 Stinger
- Provide short webm (or HTML sting) + instructions to set OBS Stinger transition.
- Keep under ~1s; brand green/black.

### P1-04 Dual cam
- Second capture source in generator; visible toggle; document hotkey.
- Layout: wheel cam smaller above/beside face OR opposite corner — propose in PR notes.

### P1-05 Ending ricco
- Discord invite URL + optional QR image path in config.
- Social row already exists; extend.

### P1-06 BRB smart
- `brbUntil` clock time; display “Torno alle HH:MM” + optional countdown.

## Out of scope

Chat/alerts (engagement), telemetry (sim-pro).
