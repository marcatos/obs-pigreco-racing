# Documentation

Guides for the **OBS PiGreco Racing** pack — local-first scene collections, branded Browser Source overlays, an **in-OBS config dock**, and optional iRacing telecronaca.

**Public overview (English):** [`../README.md`](../README.md) — includes vanity sections for the [config dock](../README.md#config-dock--change-the-stream-without-editing-files) and [telecronaca](../README.md#telecronaca--local-telemetry-on-stream).  
**Non-technical pilots (Italian):** [`../LEGGIMI.txt`](../LEGGIMI.txt) · [`../Guida_PiGreco_OBS.pdf`](../Guida_PiGreco_OBS.pdf)

---

## Start here

Get on stream fast — setup, **config dock**, personal pack.

| Doc | Summary |
|-----|---------|
| [`../LEGGIMI.txt`](../LEGGIMI.txt) | Italian double-click path (`Setup.bat`) |
| [`OBS_CONFIG_PANEL.md`](OBS_CONFIG_PANEL.md) | In-OBS dock at `:8766` — identity, session, countdown, BRB, ending, sponsors, telecronaca toggles; writes `config.values.json` |
| [`S_MARCATO_42.md`](S_MARCATO_42.md) | Personal carbon / Rosso Corsa pack |
| [`../Guida_PiGreco_OBS.pdf`](../Guida_PiGreco_OBS.pdf) | Illustrated team guide (Italian) |

---

## On-stream

Broadcast look and feel — brand tokens, transitions, cameras.

| Doc | Summary |
|-----|---------|
| [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) | Official palette, type, layout zones |
| [`STINGER.md`](STINGER.md) | Brand stinger transition |
| [`CAMERAS.md`](CAMERAS.md) | Cam PIP / Cam 2, greenscreen notes |
| [`TRANSITIONS.md`](TRANSITIONS.md) | Move / scene transition notes |

---

## Sim pro

Optional **local** telemetry stack — no cloud required. Mock or iRacing bridge → WebSocket → broadcast chrome (+ minimap); Flag Director cuts OBS on race flags.

| Doc | Summary |
|-----|---------|
| [`TELEMETRY_BROADCAST.md`](TELEMETRY_BROADCAST.md) | Bridge, standings / relative / focus / director moments, OBS HTTP sources |
| [`TRACK_MAP.md`](TRACK_MAP.md) | Peripheral minimap + self-learn outlines |
| [`FLAG_DIRECTOR.md`](FLAG_DIRECTOR.md) | Auto OBS scenes on yellow / red / checkered |
| [`../adapters/telemetry/CONTRACT.md`](../adapters/telemetry/CONTRACT.md) | WebSocket tick contract |

---

## Build / decide

Architecture, roadmap, and locked decisions for contributors and agents.

| Doc | Summary |
|-----|---------|
| [`../STRATEGY.md`](../STRATEGY.md) | Why / who / investment tracks |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, adapters, OBS boundaries |
| [`ROADMAP.md`](ROADMAP.md) | Phased IDs and acceptance |
| [`CONCEPTS.md`](CONCEPTS.md) | Shared vocabulary |
| [`adr/`](adr/) | Architecture Decision Records |
| [`workstreams/`](workstreams/) | Parallel workstream briefs |
| [`../AGENTS.md`](../AGENTS.md) | Rules for coding agents |

---

## Related

- Showcase PNGs: [`../showcase/`](../showcase/)
- StreamElements themes: [`../adapters/streamelements/README.md`](../adapters/streamelements/README.md)
- PiGreco asset attribution: [`../ATTRIBUTION.md`](../ATTRIBUTION.md)
