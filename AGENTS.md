# AGENTS.md — Working in this repo

This repository is designed for **sequential or parallel AI agents**. Read this before coding.

## Canonical docs (order)

1. [`STRATEGY.md`](STRATEGY.md) — why / who / tracks  
2. [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) — visual & brand rules  
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — layers & boundaries  
4. [`docs/ROADMAP.md`](docs/ROADMAP.md) — phases, IDs, acceptance  
5. [`docs/adr/`](docs/adr/) — locked decisions (do not silently reverse)  
6. Workstream brief in [`docs/workstreams/`](docs/workstreams/) for your task  

## How to pick work

- Claim **one** roadmap item ID (e.g. `P1-02`) or one workstream file.
- Prefer items with status `ready` over `blocked`.
- Do **not** expand scope into another workstream without updating ROADMAP + ADR if needed.
- After finishing: mark item `done`, update showcase if overlays changed, Conventional Commit.

## Hard constraints

- Canvas / overlays target **1920×1080**.
- OBS **32.x** scene transforms must set correct `pos_rel` / `scale_rel` (see `tools/generate_pack.py`).
- Brand colors from official site: green `#00C400`, blue `#009FE5`, bg `#080A0C`.
- Streamer-facing setup must stay usable via **`Setup.bat`** for non-technical pilots.
- No GitHub remote required; local git + Conventional Commits.
- Do not commit secrets; do not log tokens in setup logs.

## Overlay conventions

- Config surface: `overlays/config.js` (+ `config.example.js` kept in sync for new keys).
- Shared look: `overlays/assets/theme.css`.
- Behavior modules: small JS files (`sponsors.js`, `countdown.js`, …) loaded after `config.js`.
- Prefer Browser Source HTML over baking graphics into OBS image sources.

## Regeneration

```powershell
python tools/generate_pack.py          # OBS JSON + logo sync
python tools/generate_showcase.py      # PNG previews
python tools/generate_pdf_guide.py     # Guida PDF
.\Setup.ps1 -Username …                # end-user install path
```

Close OBS before rewriting `PiGreco_Racing.json`.

## Parallel agents

Safe parallel pairs (little file overlap):

| Agent A | Agent B |
|---------|---------|
| `ws-broadcast-polish` overlays | `ws-docs-packaging` PDF/README |
| `ws-engagement` chat CSS templates | `ws-sim-pro` SimHub notes (docs-only until APIs land) |

Avoid two agents editing `tools/generate_pack.py` or `obs/PiGreco_Racing.json` at once.
