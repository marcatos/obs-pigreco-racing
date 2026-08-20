# Telecronaca broadcast (P3-02)

Live standings, focus car, and flag context on stream — without leaving the local machine. A **local iRacing (or mock) bridge** pushes ticks over WebSocket into brand HTML (broadcast chrome); optional SimHub / Racing Overlay can sit beside it as extra Browser Sources.

**On the public README:** product-facing overview of the stack (chrome widgets, track map, flag director, one-bat launchers) lives under [Telecronaca](../README.md#telecronaca--local-telemetry-on-stream). This page is the operator deep dive.

Pipeline: **local bridge** → WebSocket [`CONTRACT`](../adapters/telemetry/CONTRACT.md) → brand HTML overlay.

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
`CarIdxLap` + `CarIdxLapDistPct`. In **live race** (after rolling-start hold) it also
uses lap + distPct so a brief missing `CarIdxPosition` at S/F cannot flip the whole
board to official order and back. Quali / practice still prefer official positions when
enough cars report `> 0`.

### Optional IBT recording (native Motec / Mu)

The bridge does **not** invent `.ibt` bytes — it asks the sim to start/stop disk
telemetry via SDK `telem_command` (same as Alt+L):

```powershell
.\Start-Telemetry.bat iracing --ibt
# oppure:
python adapters/telemetry/iracing_bridge.py --ibt
```

Files appear under `Documents\iRacing\telemetry\` when the driver is **in-car**.
In pure replay/spectator the sim often writes nothing — use live sessions for Motec.

Do **not** autostart the bridge from OBS scripting (console flash / fragile Python).

## OBS sources

| Collection | Scenes | Sources (eye off by default unless noted) |
|------------|--------|-------------------------------------------|
| S.Marcato Replay | Replay *, Rec * Live | Overlay Broadcast Chrome (includes minimap when `trackMapEnabled`) |
| S.Marcato Rec 2K | Rec * Live | same (scaled ×4/3) |
| Both packs | Live / Replay live scenes | Transparent Flag FX overlay (telemetry) |
| Replay / Rec 2K | Flag Yellow / Red / Checkered (optional) | Same gameplay + telecronaca + forced flag FX |

**URL obbligatorie** (non `file://` — CEF/OBS spesso non apre il WebSocket da file locali):

```
http://127.0.0.1:8766/o/marcato/broadcast-chrome.html
```

Serve il **config server** acceso (`Start-ConfigPanel.bat` o script Lua in OBS).  
One full-frame Browser Source — minimap is embedded when `trackMapEnabled` (optional standalone `track-map.html` remains).

Layout (periferico, niente centro FOV):

| Zona | Widget |
|------|--------|
| Top center | Session badge + FIELD-like **flag strip** (rise → expand L→R → hold → collapse → drop) |
| Left rail | Focus (camera) + Battle relative (`AHD` / `CAM` / `BHD`) |
| Top right | Standings |
| Mid-right (above Cam 2) | Track minimap |
| Bottom edge | NASCAR-style scrolling field ticker (`broadcastTicker`); shows `clubName` when present |
| Bottom center | Live **Battle for Px** pack when gaps are close (`broadcastBattlePanel`) |

Focus shows **S1–Sn** sector chips + live **Δ** when the bridge emits P3-08 fields (`sectors`, `sector`, `sectorDeltaMs`, `deltaLiveMs`). On iRacing, live sector times need the camera on the **player** car; geometry ticks still appear on the map for any focus.

## Config keys

See `overlays/config.example.js`:

- `telemetryEnabled` (default `false`)
- `telemetryWsUrl` (default `ws://127.0.0.1:8765`)
- `broadcastLeaderboard` / `Relative` / `Focus` / `Session` / `Ticker`
- `broadcastLeaderboardRows` (5–20)
- `broadcastBoardRefreshMs` (default `4000`) — TV-style refresh for standings **gaps** and the relative panel; order + ▲/▼ vs **starting grid** stay live
- `broadcastTicker` (default `true`) — bottom field strip; **rise** (FIELD only) → **expand** right → scroll once P1→last → **collapse** to FIELD → **drop** down; then wait `broadcastTickerIdleMs`
- `broadcastTickerSpeed` (default `85`) — scroll speed in px/sec while visible
- `broadcastBattlePanel` (default `true`) — bottom-center horizontal fight pack (monogram + generic helmets); arms when a neighbour is **closing fast** (gap shrink rate) within engage range; pack only shows cars within a tighter include gap (~0.26s normal)
- Battle pack arms only when `battleEligible` is true: **race** after live order (lap ≥ 1, not formation/pace); **practice** with ≥1 other car; **never** in quali/cooldown.
- `broadcastBattleMs` / `broadcastBattleTicks` — optional overrides (0 = use `broadcastDirectorSensitivity`)
- `broadcastTickerFirstDelayMs` (default `4000`) — delay before first appearance
- `broadcastFlagStripMs` (default `10000`, clamp 2000–30000) — hold time for **timed** flags (`white` / `debris` / `checkered`) before the strip collapses even if the SDK flag is still set
- `broadcastDirector` (`auto` | `manual` | `off`, default `auto`)
- `broadcastDirectorSensitivity` (`calm` | `normal` | `hype`, default `normal`)

### Flag strip (P3-12)

Top full-width strip owns flag UX (replaces `.bc-flag-banner` and flag moment chips). Choreography matches the field ticker: **rise** → **expand** L→R → **show** → **collapse** → **drop**.

| `tick.flag` | Label | Body | Timing |
|-------------|-------|------|--------|
| `white` | LAST LAP | FINAL LAP | Timed: `broadcastFlagStripMs` then hide (does not re-enter while SDK stays white) |
| `debris` | DEBRIS | DEBRIS ON TRACK | Timed, same |
| `checkered` | CHECKERED | SESSION FINISH | Timed, same |
| `yellow` | YELLOW | CAUTION | Hold while active; hide on green/none |
| `red` | RED | SESSION STOPPED | Hold while active; hide on green/none |
| `blue` | BLUE | LET LEADER BY | Hold while active; hide on green/none |

`telemetry.event` `flag_change` / `session_end` update the strip and **do not** enqueue director moment chips. Refresh mid-flag still syncs from `tick.flag`.

Race rolling starts: the bridge holds grid order through formation / pace and until enough cars have crossed S/F (`lap >= 1`), so the first timing-line chaos after the pace car does not reshuffle the board.

`broadcastDirectorSensitivity` is stored for future client-side filters. **Detection** lives on the producer (`python adapters/telemetry/mock_server.py --sensitivity hype` or the iRacing bridge). The overlay does not dual-detect.

## Broadcast director (P3-06)

Hybrid auto/manual moments on the same Browser Source. Base widgets (session, focus, standings, relative) follow existing toggles; a moment chip plays above the session strip (not center FOV). Flag moments are the top strip, not chips.

### Director modes

| Mode | Behavior |
|------|----------|
| `auto` | Widget toggles = **allow-list**. Director shows/hides and plays moments from `telemetry.event`. Session + focus stay on if toggled. |
| `manual` | Only toggles; ignore `telemetry.event` for hero UI (events may still arrive on the socket). |
| `off` | No moment layer; base follows toggles only (same as today’s static layout). |

`telemetryEnabled: false` still means no WebSocket (unchanged).

### Events are WebSocket-only

`telemetry.event` frames (`flag_change`, `battle`, `overtake`, `fast_lap`, `pit`, `session_end`) are emitted on the **WebSocket** after the tick that produced them. File mode (`--mode file`) stores the latest tick only — events are **not** persisted.

`battle` is **edge-triggered**: one chip when the fight starts (gap stays under the sensitivity threshold for a short streak). While the gap stays close, no more `BATTLE` heroes — the relative/battle panel already shows the fight. A new chip can fire only after the gap opens again (with a bit of hysteresis so threshold jitter does not re-arm). Near start/finish (`distPct` < 0.04 or > 0.96) battle arming is muted because estimated gaps thrash on the timing line.

`overtake` requires the improved focus position to hold for **3 ticks** (single-tick S/F reshuffles are ignored) and is also muted in that S/F corridor. `fast_lap` / FASTEST only fires on a true personal best (`lastLapMs` beats the previous `bestLapMs`).

Mock scripted windows (elapsed seconds):

| Window | What you should see (`auto`) |
|--------|------------------------------|
| `int(t) % 47` in 12–14 | Yellow flag strip (holds until green; no `YELLOW` chip) |
| `int(t) % 80` in 40–44 | Focus `inPit`; `PIT ENTER` then `PIT EXIT` |
| `int(t) % 113 == 0` | White / checkered strip (~10s) + `session_end` (strip only, no finish chip) |

### Smoke checklist (auto vs manual)

1. Config panel: `telemetryEnabled` on, `broadcastDirector: auto`. Start mock (`.\Start-Telemetry.bat mock`).
2. OBS / browser: yellow around ~12s → top flag strip (YELLOW / CAUTION), no moment chip. Green clears it.
3. White / debris / checkered → strip ~10s then drop even if the mock flag stays set.
4. Pit window around ~40s → `PIT ENTER` / `PIT EXIT` (blue chip accent).
5. Switch `broadcastDirector` to `manual` or `off` → no hero chips; strip still follows `tick.flag`; widget toggles still apply.
6. `telemetryEnabled: false` → overlay does not open a WebSocket.

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
| `adapters/telemetry/mock_server.py` | Fake ticks + scripted events |
| `adapters/telemetry/iracing_bridge.py` | iRacing → WS |
| `adapters/telemetry/domain_standings.py` | Standings helpers |
| `adapters/telemetry/domain_events.py` | `telemetry.event` detection (no IO) |
| `overlays/broadcast-chrome.html` | PiGreco UI |
| `overlays-marcato/broadcast-chrome.html` | S.Marcato UI |
| `overlays/broadcast-director.js` | Overlay director queue / labels |
| `docs/adr/005-telemetry-adapter-port.md` | Architecture ADR |

## Acceptance

- Mock: leaderboard + focus animate in Browser Source
- Mock `broadcastDirector: auto`: flag strip for yellow/white/checkered; pit chips play; `manual`/`off` hide chips (strip still follows ticks)
- Replay: positions/gaps roughly match the sim
- Pack works with bridge off and `telemetryEnabled: false`
