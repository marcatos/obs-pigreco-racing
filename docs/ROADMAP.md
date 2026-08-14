# Roadmap

Status legend: `done` · `in_progress` · `ready` · `blocked` · `later`

Update this file when claiming or finishing an ID.

## Phase 0 — Pack core (baseline)

| ID | Item | Status |
|----|------|--------|
| P0-01 | Scene collection 5 scene + StreamCam + monitor dual | done |
| P0-02 | Brand overlays + official assets | done |
| P0-03 | Sponsor rotator discreto | done |
| P0-04 | Setup.bat/ps1 + Python elevate | done |
| P0-05 | Guida PDF brand + showcase | done |
| P0-06 | Multi-agent scaffolding (this docs set) | done |
| P0-07 | OBS Config Panel (Custom Browser Dock) | done | `Start-ConfigPanel.bat` + :8766 |

## Phase 1 — Broadcast polish (visual)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P1-01 | Countdown Starting Soon | done | `goLiveAt` / `countdownSeconds` |
| P1-02 | Badge sessione (Practice/Quali/Race) | done | pill top-center |
| P1-03 | Stinger transition (webm/mov or HTML) | done | `overlays/stinger/` + `docs/STINGER.md` |
| P1-04 | Dual cam layout (face + wheel) toggle | ready | second dshow + hotkey hide |
| P1-05 | Ending ricco (Discord QR + CTA) | done | config URLs + QR PNG |
| P1-06 | BRB smart timer “torno alle HH:MM” | done | `brbUntil` + optional countdown |

## Phase 2 — Engagement

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P2-01 | Chat overlay theme PiGreco | done | `adapters/streamelements/chat.css` |
| P2-02 | Alert box theme (follow/sub/raid) | done | `adapters/streamelements/alerts/` |
| P2-03 | Hotkey map + Stream Deck profile export | ready | JSON/docs |
| P2-04 | Instant Replay / Highlight scene | ready | replay buffer media source |

## Phase 3 — Sim pro

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P3-01 | Telemetry bridge design (SimHub/iRacing) | done | ADR-005 + mock `adapters/telemetry/` |
| P3-02 | Live relative / position widget | done | broadcast-chrome + mock + iracing_bridge; docs/TELEMETRY_BROADCAST.md |
| P3-03 | Minimap / track map | later | |
| P3-04 | Auto scene on flags | later | obs-websocket |
| P3-05 | Audio buses + VOD track guide | ready | docs + OBS profile notes |

## Phase 4 — Team distribution

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P4-01 | Setup wizard UI (WinForms/WebView) | later | |
| P4-02 | Game presets (iRacing/ACC/LMU) | ready | config profiles JSON |
| P4-03 | Pack lite (prebuilt, no Python) | later | |
| P4-04 | Personal pack S.Marcato 42 | done | `overlays-marcato/`, `obs/S_Marcato_42.json`, `docs/S_MARCATO_42.md` |

## Suggested next agent claims

1. `P1-04` Dual cam layout (second dshow + hotkey)  
2. `P2-03` hotkey map + Stream Deck  
3. `P3-03` minimap (later) / `P3-05` audio buses + VOD track guide  
4. Showcase PNG for broadcast chrome when widgets are stable on stream  

## Definition of done (any ID)

- [ ] Behavior matches acceptance in workstream brief  
- [ ] `config.example.js` updated if new keys  
- [ ] Showcase regenerated if visible overlay change  
- [ ] Conventional Commit  
- [ ] ROADMAP status → `done`  
