# Design — Marcato live slim + Session Director

**Date:** 2026-08-14  
**Status:** approved  
**Roadmap:** P2-03 (VirtualDeck/hotkey map), P3-04 extension (Session Director), P3-05 notes (audio beds)

## Goal

Clean **S.Marcato 42** into a slim live collection that reuses Replay telecronaca graphics, auto-switches **Live ↔ Lobby**, auto-starts iRacing telemetry when the sim is open, and is fully controllable from **OBS VirtualDeck** (OBS WebSocket).

## Scene model (S.Marcato 42 only)

| Scene | Role |
|-------|------|
| Starting Soon | Pre-show interstitial + music |
| Live | Monitor Centro + live chrome + broadcast telecronaca + cam |
| Lobby | iRacing UI capture + music (sim open, no telemetry) |
| BRB / Ending | Interstitials + music |
| Flag Yellow / Red / Checkered | Full-screen flag cuts |

Removed from this collection: Live Race, Live Singolo, Live Triplo, Rec *.  
**S.Marcato Replay** and **Rec 2K** stay for recording / replay streaming.  
**PiGreco Racing** pack unchanged.

## Capture

- **Live:** Monitor Centro only (works with triple-screen; center gameplay).
- **Lobby:** Window capture of iRacing UI (`iRacingUI.exe`), not `iRacingSim64DX11.exe`.

## Session Director

Extends Flag Director (same adapter):

1. iRacing process up + telemetry WS down → start telemetry (`iracing` mode), no restart spam.
2. Telemetry connected → `Live` (unless on Flag *).
3. iRacing up + telem lost (debounce ~4s) → `Lobby`.
4. Flags Y/R/C → Flag scenes; green/none → stacked home (`Live` or `Lobby`).
5. Never auto-leave Starting Soon / BRB / Ending (manual / VirtualDeck only).

## Audio

- Desktop = race / system; Mic = Focusrite 2i2 (resolvable device id).
- Beds: Starting Soon, Lobby, BRB, Ending (synthesized MP3s in-repo).
- Live: no music bed.

## VirtualDeck

OBS 28+ built-in WebSocket `:4455`. Doc + button map for slim scenes. Password only in gitignored `config.local.json`.
