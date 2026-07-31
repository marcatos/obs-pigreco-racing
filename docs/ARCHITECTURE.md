# Architecture

## Intent

Keep **domain/config** free of OBS/file IO where practical; put generation and install at the edges. Overlays are the “UI adapter” for the stream.

```mermaid
flowchart TB
  subgraph domain [Domain]
    Config[StreamerConfig]
    Session[SessionBadgeCountdown]
    Sponsors[SponsorRotation]
  end
  subgraph app [Application]
    SetupUseCase[SetupStreamer]
    PackGen[GenerateObsPack]
    ShowcaseGen[GenerateShowcase]
  end
  subgraph adapters [Adapters]
    HTML[Browser Overlay HTML/JS]
    OBSJSON[OBS Scene Collection JSON]
    PS1[Setup.ps1 / winget]
    PDF[PDF Guide]
  end
  Config --> HTML
  Session --> HTML
  Sponsors --> HTML
  SetupUseCase --> Config
  SetupUseCase --> PackGen
  PackGen --> OBSJSON
  ShowcaseGen --> HTML
  PS1 --> SetupUseCase
```

## Layers

| Layer | Location | May depend on |
|-------|----------|----------------|
| Domain ideas | `overlays/config.js` shape, docs/CONCEPTS | nothing external |
| Overlay UI | `overlays/*.html`, `*.js`, `assets/theme.css` | config only |
| Tools / use cases | `tools/*.py` | filesystem, Pillow, Chrome |
| Install adapter | `Setup.ps1`, `Setup.bat` | winget, Python, OBS AppData |
| OBS artifact | `obs/PiGreco_Racing.json` | generated, not hand-edited long-term |

## Rules

1. **Regenerate, don’t hand-edit** OBS JSON for layout math — change `tools/generate_pack.py`.
2. New on-stream widgets = new small JS module + CSS in theme + config keys.
3. Official logos live under `overlays/assets/official/`; processed copies in `overlays/assets/`.
4. Telemetry (Phase 3) must enter via a **port** (e.g. local websocket/file) — never hardcode a sim SDK inside HTML forever without an adapter folder (`adapters/telemetry/` planned).

## Planned folders (create when first needed)

```
adapters/
  telemetry/          # SimHub / iRacing bridges
  streamelements/     # CSS/theme exports
  streamdeck/         # profile exports
overlays/
  modules/            # optional future home for JS modules
docs/
  workstreams/
  adr/
```

## OBS specifics

- Profile canvas **1920×1080**.
- Relative transforms required (OBS 32): see `pos_rel` helpers in `generate_pack.py`.
- Browser Sources use `file:///` URLs absolute to install path — regen after move.
