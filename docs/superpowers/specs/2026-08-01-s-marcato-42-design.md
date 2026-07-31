# S.Marcato 42 — Personal OBS Pack Design

Date: 2026-08-01  
Status: Approved (conversation) — pending user review of this file  
Owner: Simone Marcato (`@senormarcato`)

## Problem

Need a **personal** OBS broadcast pack alongside the existing PiGreco Racing team pack:

- No PiGreco branding
- No sponsor rotator
- Same operational features (scenes, countdown, BRB, ending, config, stinger)
- Adult / modern racing aesthetic (CTO, ~37) — not neon teen-streamer graphics

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Packaging | **A** — separate OBS scene collection + dedicated overlay folder |
| Visual | Carbon + white + single **steel/silver** accent |
| Brand mark | Typographic only: **`S.MARCATO`** + **`42`** as race number |
| Ending CTA | Twitch follow `@senormarcato` (no Discord QR) |
| Implementation shape | Overlay twin + shared JS where sensible (Approach 1) |

## Goals

- Switch in OBS to collection **«S.Marcato 42»** with zero PiGreco assets on screen
- Preserve: Starting Soon, Live Race, Live Singolo, BRB, Ending
- Preserve: countdown, session badge, BRB return timer, config panel workflow, stinger
- Center FOV of gameplay remains clear (chrome at edges only)

## Non-goals

- Removing or redesigning the PiGreco pack
- Native C++ OBS plugin
- New telemetry widgets beyond what PiGreco already ships
- Invented pictorial logo / mascot
- Sponsor slots (even empty placeholders) on Marcato overlays

## Architecture

```
obs-pigreco-racing/
  overlays/                 # PiGreco (unchanged behavior)
  overlays-marcato/         # Personal twin
    assets/theme.css        # Carbon / steel tokens + fonts
    starting-soon.html
    live-chrome.html
    brb.html
    ending.html
    stinger/
    config.values.json      # sponsorsEnabled: false, personal copy
    … shared script copies or thin wrappers importing ../overlays/*.js
  obs/
    PiGreco_Racing.json     # existing
    S_Marcato_42.json       # new scene collection → overlays-marcato paths
```

### Config

- Canonical values: `overlays-marcato/config.values.json`
- Defaults: `pilotName` / wordmark `S.Marcato`, number `42`, `twitchHandle` `@senormarcato`, `sponsorsEnabled: false`, `teamName` empty or omitted from UI
- Ending: CTA text for Twitch follow; no Discord QR fields required (can leave unused keys out or disabled)
- Config panel: either profile switcher later, or second URL/path — **v1:** point panel at Marcato values when using Marcato collection (document how; prefer same server with `?profile=marcato` or separate port only if needed). Minimum viable: setup writes Marcato JSON; panel can load/save Marcato path via query `?config=marcato`.

### Scene collection

Mirror PiGreco scenes/sources structure; Browser Sources use `overlays-marcato/*.html`. Same 1920×1080 canvas assumptions. Transform rules unchanged (generator-aware if pack is regenerated).

## Visual system

### Color

| Token | Role | Approx |
|-------|------|--------|
| `--bg` | Carbon void | `#0A0B0D` |
| `--panel` | Soft carbon | `#121417` |
| `--text` | Primary | `#F2F4F6` |
| `--muted` | Secondary | `#8B939C` |
| `--steel` | Sole accent | `#C5CCD4` |
| `--steel-dim` | Hairlines | `rgba(197,204,212,0.35)` |
| `--line` | Borders | `rgba(255,255,255,0.10)` |

No green, no PiGreco blue, no gold, no neon glow, no purple gradients.

### Typography

- Display: geometric modern (e.g. **Syne** or **Space Grotesk**) — not Orbitron
- Body/UI: **IBM Plex Sans** (or equivalent readable grotesque)
- Lockup: `S.MARCATO` large; `42` smaller, tabular, treated as race number (not a hashtag)

### Layout principles

- One composition per interstitial (Starting / BRB / Ending): brand, one headline, one support line, optional timer/CTA — no card stacks, no badge clutter
- Live chrome: thin edge elements (session badge, optional lower-third name/number); no center overlays
- Motion: short fade/slide 200–400ms; no flash stingers; stinger = steel wipe / opacity mask, restrained

### Copy defaults (Italian, sober)

- Starting: short status (`IN DIRETTA A BREVE` or equivalent), not hype slang
- BRB: `TORNO SUBITO` + optional `TORNO ALLE HH:MM`
- Ending: `GRAZIE` + follow `@senormarcato`
- Tagline example: `Sim racing · Broadcast`

## Feature parity matrix

| Feature | Marcato |
|---------|---------|
| Starting countdown | Yes |
| Session badge | Yes (steel styling) |
| Live chrome lower-third | Yes — `S.MARCATO` / `42` |
| Sponsor rotator | **No** (disabled, scripts not mounted) |
| BRB timer | Yes |
| Ending Twitch CTA | Yes |
| Ending Discord QR | **No** |
| Stinger | Yes (restyled) |
| Config panel | Yes (Marcato config path) |
| Telemetry stub | Optional; off by default like PiGreco |

## Acceptance criteria

- [ ] OBS collection `S.Marcato 42` imports and shows five scenes
- [ ] No PiGreco wordmark, green/blue brand colors, or sponsor logos appear
- [ ] Interstitials and live chrome match carbon/steel system
- [ ] Countdown / session / BRB / Twitch ending CTA work via Marcato config
- [ ] PiGreco collection still works unchanged
- [ ] Short doc: how to switch collections + config for Marcato
- [ ] Showcase or screenshot note for Marcato (optional but preferred)

## Open points (resolve in plan if needed)

1. Config panel: `?profile=marcato` on same `:8766` vs duplicate — prefer **same server + profile query**
2. Whether `generate_pack.py` gains a Marcato target or Marcato JSON is hand-templated from PiGreco once
3. Exact Google Fonts pair final names at implementation time (within system above)

## Out of scope for v1

- Stream Deck profile
- Dual cam layout
- Separate GitHub repo / public distribution
