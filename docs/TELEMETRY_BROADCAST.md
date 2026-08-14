# Telecronaca broadcast (P3-02)

Hybrid pack: **local iRacing bridge** → WebSocket CONTRACT → brand HTML overlay.
Optional third-party tools (SimHub / Racing Overlay) can sit beside it as extra Browser Sources.

## Quick start (mock — no iRacing)

```powershell
pip install -r adapters/telemetry/requirements.txt
# Preferito (entry non tecnico):
.\Start-Telemetry.bat mock
# oppure:
python adapters/telemetry/mock_server.py
```

1. Config panel → enable **Overlay broadcast attivo** (`telemetryEnabled`).
2. OBS: scene Replay / Rec * Live → eye on **Overlay Broadcast Chrome**.
3. Open `overlays-marcato/broadcast-chrome.html` (or PiGreco twin) in a browser to smoke-test.

With `telemetryEnabled: false` the overlay does **not** open a WebSocket.

## iRacing (replay first, then live)

```powershell
pip install -r adapters/telemetry/requirements.txt
# Close any mock_server on the same port first
.\Start-Telemetry.bat iracing
# oppure:
python adapters/telemetry/iracing_bridge.py
```

1. Open iRacing replay (`.rpy`) or a live/spectator session.
2. Start the bridge (external process — **not** an OBS Python script).
3. Enable `telemetryEnabled` in the config panel and show **Overlay Broadcast Chrome**.

Replay note: SDK `CarIdxPosition` is often wrong in replay. The bridge ranks cars by
`CarIdxLap` + `CarIdxLapDistPct`. In live it prefers official positions when enough
cars report `> 0`.

Do **not** autostart the bridge from OBS scripting (console flash / fragile Python).

## OBS sources

| Collection | Scenes | Source |
|------------|--------|--------|
| S.Marcato Replay | Replay *, Rec * Live | Overlay Broadcast Chrome (eye **off** by default) |
| S.Marcato Rec 2K | Rec * Live | same (scaled ×4/3) |

One full-frame Browser Source (`broadcast-chrome.html`) — not five separate widgets.

## Config keys

See `overlays/config.example.js`:

- `telemetryEnabled` (default `false`)
- `telemetryWsUrl` (default `ws://127.0.0.1:8765`)
- `broadcastLeaderboard` / `Relative` / `Focus` / `Session`
- `broadcastLeaderboardRows` (5–20)

## Optional: SimHub / Racing Overlay (fase D)

Keep the pack brand chrome as the primary overlay. Add third-party maps or
dashboards as **extra** Browser Sources on the same scene:

1. Leave **Overlay Broadcast Chrome** (or Live/Replay chrome) as-is.
2. Add a Browser Source pointing at the SimHub / Racing Overlay URL
   (often `http://localhost:…` from that app’s docs).
3. Size and place it in a **safe zone** (top-right / side band) — never cover
   the center FOV of the race view.
4. Use the eye icon to toggle map vs our leaderboard independently.

Do **not** replace `broadcast-chrome.html` with a third-party full HUD if you
want S.Marcato / PiGreco brand consistency. Prefer:

- Our pack: standings / focus / session / flags
- SimHub or Racing Overlay: track map, advanced relative, dash gauges

Same idea works on Rec 2K: design the third-party page at 1920×1080 and scale
the Browser Source like the other overlays, or native 2560×1440 if the tool allows.

## Files

| Path | Role |
|------|------|
| `adapters/telemetry/CONTRACT.md` | Message schema |
| `adapters/telemetry/mock_server.py` | Fake ticks |
| `adapters/telemetry/iracing_bridge.py` | iRacing → WS |
| `adapters/telemetry/domain_standings.py` | Standings helpers |
| `overlays/broadcast-chrome.html` | PiGreco UI |
| `overlays-marcato/broadcast-chrome.html` | S.Marcato UI |
| `docs/adr/005-telemetry-adapter-port.md` | Architecture ADR |

## Acceptance

- Mock: leaderboard + focus animate in Browser Source
- Replay: positions/gaps roughly match the sim
- Pack works with bridge off and `telemetryEnabled: false`
