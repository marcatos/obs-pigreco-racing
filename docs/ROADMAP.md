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
| P0-05 | Guida PDF brand + showcase | done | maintain: EN vanity README + docs hub; config/telecronaca sections (2026-08-14) |
| P0-06 | Multi-agent scaffolding (this docs set) | done |
| P0-07 | OBS Config Panel (Custom Browser Dock) | done | `Start-ConfigPanel.bat` + :8766 |

## Phase 1 — Broadcast polish (visual)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P1-01 | Countdown Starting Soon | done | `goLiveAt` / `countdownSeconds` |
| P1-02 | Badge sessione (Practice/Quali/Race) | done | pill top-center |
| P1-03 | Stinger transition (webm/mov or HTML) | done | `overlays/stinger/` + `docs/STINGER.md` |
| P1-04 | Dual cam layout (face + wheel) toggle | done | Cam PIP + Cam 2 PIP, NVIDIA greenscreen chair + carbon BG; `docs/CAMERAS.md`; cam device ID refresh 2026-08-15 |
| P1-05 | Ending ricco (Discord QR + CTA) | done | config URLs + QR PNG |
| P1-06 | BRB smart timer “torno alle HH:MM” | done | `brbUntil` + optional countdown |

## Phase 2 — Engagement

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P2-01 | Chat overlay theme PiGreco | done | `adapters/streamelements/chat.css` |
| P2-02 | Alert box theme (follow/sub/raid) | done | `adapters/streamelements/alerts/` |
| P2-03 | Hotkey map + Stream Deck / VirtualDeck profile | done | `adapters/streamdeck/marcato-live-deck.json`, `docs/OBS_VIRTUALDECK.md` |
| P2-04 | Instant Replay / Highlight scene | ready | replay buffer media source |
| P2-05 | YouTube like/subscribe/bell promo | done | `youtube-promo.js` in live-chrome; config `youtubePromo*` |

## Phase 3 — Sim pro

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P3-01 | Telemetry bridge design (SimHub/iRacing) | done | ADR-005 + mock `adapters/telemetry/` |
| P3-02 | Live relative / position widget | done | broadcast-chrome + mock + iracing_bridge; docs/TELEMETRY_BROADCAST.md |
| P3-03 | Minimap / track map | done | `track-map.html`; open+self-learn; `docs/TRACK_MAP.md` |
| P3-04 | Auto scene on flags | done | `adapters/obs_flag_director/`, `docs/FLAG_DIRECTOR.md` — extended by Session Director (Live↔Lobby) |
| P3-05 | Audio buses + VOD track guide | done | interstitial + lobby beds; mixer notes in `SESSION_DIRECTOR.md` / `S_MARCATO_42.md` |
| P3-06 | Broadcast director + tick enrichment | done | spec 2026-08-14; hybrid auto/manual moments |
| P3-07 | Official iRacing SVG track maps | done | sync CLI + local cache; overlay SVG; `docs/TRACK_MAP.md` |
| P3-08 | Sector timing on broadcast chrome | done | SplitTimeInfo + live Δ; focus S1–Sn; map ticks |
| P3-09 | NASCAR-style field ticker | done | bottom scroll strip; `broadcastTicker` |
| P3-10 | Live Battle for Px panel | done | bottom-center fight pack; show/hide on close gaps |
| P3-11 | Race best lap panel | done | field best so far + driver; right of session strip |
| P3-12 | Flag strip + battle session gate + cam ID refresh | in_progress | spec 2026-08-15-marcato-cam-flag-battle-design |

## Phase 4 — Team distribution

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P4-01 | Setup wizard UI (WinForms/WebView) | later | |
| P4-02 | Game presets (iRacing/ACC/LMU) | ready | config profiles JSON |
| P4-03 | Pack lite (prebuilt, no Python) | later | |
| P4-04 | Personal pack S.Marcato 42 | done | `overlays-marcato/`, `obs/S_Marcato_42.json`, `docs/S_MARCATO_42.md` |

## Suggested next agent claims

1. `P3-12` Flag strip + battle session gate + cam ID refresh (Tasks 2–6 after Task 1 debris bits)
2. Showcase PNG for broadcast chrome when widgets are stable on stream
3. `P2-04` Instant Replay / Highlight scene
4. `P4-02` Game presets  

## Definition of done (any ID)

- [ ] Behavior matches acceptance in workstream brief  
- [ ] `config.example.js` updated if new keys  
- [ ] Showcase regenerated if visible overlay change  
- [ ] Conventional Commit  
- [ ] ROADMAP status → `done`  
