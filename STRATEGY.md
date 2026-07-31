---
last_updated: 2026-07-31
product: obs-pigreco-racing
---

# Strategy — OBS PiGreco Racing

## Target problem

I piloti del team PiGreco Racing (e streamer amici) devono andare in diretta sim racing su Twitch con un look **coerente al brand**, senza essere tecnici OBS. Oggi o improvvisano scene grezze, o dipendono da setup personali non ripetibili.

## Our approach

Un **pacchetto OBS condivisibile** (scene + overlay HTML locali + setup Windows) che:

1. Si installa con doppio clic (`Setup.bat`), anche senza Python preinstallato.
2. Si personalizza con pochi campi (`username`, testi, sponsor).
3. Cresce per **fasi** (visivo → streamer UX → telemetria pro), senza rompere le scene base.
4. Mantiene un **design system** unico (palette ufficiale, overlay browser, canvas 1920×1080).

Non siamo un SaaS overlay cloud: restiamo **file locali + OBS**, semplici da zippare e passare in Discord.

## Who it's for

| Persona | Bisogno |
|---------|---------|
| Pilota team (non tecnico) | Setup.bat + PDF, poche scelte |
| Streamer / CTO del pack | Estendere overlay, config, tool Python |
| Agente AI / contributor | Roadmap + ADR + rules Cursor per non divergere |

## Key metrics

- Tempo da zip → prima preview OBS utile **&lt; 10 minuti** (pilota medio).
- Scene Live leggibili: gameplay dominante, chrome **discreto** (sponsor/telemetria non coprono il centro).
- Un solo brand recognisable (π verde + wordmark) in ogni scena pubblica.
- Zero regressioni sul layout OBS 32 (`pos_rel` / canvas 1080p).

## Tracks (investment)

1. **Pack core** — scene, brand, setup, guida, parametrizzazione (fatto / mantenere).
2. **Broadcast polish** — countdown, badge sessione, stinger, dual cam, ending ricco, BRB smart.
3. **Engagement** — chat/alert theme, hotkeys/Stream Deck, replay highlight.
4. **Sim pro** — SimHub/telemetria, minimappa, auto-scene, audio bus/VOD.
5. **Team distribution** — wizard UI, preset gioco, pack lite senza Python.

## Not working on (for now)

- App mobile / cloud hosting obbligatorio degli overlay.
- Sostituire OBS con altro software.
- Monetizzazione / store pubblico (pack interno team).
- Supporto ufficiale macOS/Linux (Windows-first).

## Milestones (coarse)

| When | Outcome |
|------|---------|
| Now | Scaffold multi-agente + Phase 1 (countdown/badge) avviata |
| Next | Stinger + BRB timer + ending social |
| Later | Chat/alert theme + Stream Deck profile |
| Stretch | Telemetria SimHub + auto flags |

Dettaglio esecutivo: [`docs/ROADMAP.md`](docs/ROADMAP.md).
