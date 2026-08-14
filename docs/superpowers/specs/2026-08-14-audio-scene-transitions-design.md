# Audio-aware scene transitions (S.Marcato 42)

**Date:** 2026-08-14  
**Status:** approved for planning  
**Approach:** OBS-native only (no Advanced Scene Switcher, no WebSocket volume ramps)

## Goal

Scene changes should dissolve the **full scene mix** (interstitial beds, Desktop, mic when present) with the video, and use a branded **stinger + whoosh** only for highlight landings (Live, Ending).

## Behaviour

| Change | Transition | Audio |
|--------|------------|--------|
| Default (any scene pair) | **Dissolvenza 900 ms** | Native OBS crossfade of sources leaving / entering over 900 ms |
| Switching **to Live** or **to Ending** | **S.Marcato Stinger** (~850 ms WebM + muxed whoosh) | Scene mix crossfade (`audio_fade_style` = crossfade) + whoosh on the stinger |
| Emergency | **Taglio** 0 ms | Hard cut |

Move Transition remains in the collection as an optional alternate; it is **not** the default (Move morphs video well but is a poor default when the priority is predictable audio dissolve).

## Scope

- **In:** `S.Marcato 42` via `tools/generate_pack.py` (`build_marcato_live_collection` + shared `build_transitions`).
- **In:** docs `TRANSITIONS.md`, short notes in `SESSION_DIRECTOR.md` / `S_MARCATO_42.md`.
- **Optional align:** Replay collection same default Dissolvenza + stinger overrides if those scenes exist; Rec 2K only if low-cost.
- **Out:** Session Director volume scripting; Advanced Scene Switcher; changing PiGreco defaults unless shared helper naturally applies.

## Implementation notes

### Pack defaults

- `current_transition` = `Dissolvenza` (`fade_transition`)
- `transition_duration` = `900`
- Quick transitions: Dissolvenza 900 · S.Marcato Stinger · Taglio (Move optional in list, not required on dock)

### Media beds

- Keep one Media Source instance per bed, referenced from interstitial scenes only (existing pattern).
- During a timed Fade, OBS keeps both scenes alive → mix crossfades without extra plugins.
- Prefer settings that do **not** hard-kill audio mid-transition; validate `close_when_inactive` / `restart_on_activate` against real OBS 32 behaviour during 900 ms fades (adjust only if cuts remain).

### Highlight overrides

- Scene **transition override** when switching **to** `Live` and **to** `Ending` → `S.Marcato Stinger`.
- Stinger already ships Opus whoosh in `overlays-marcato/stinger/marcato-stinger.webm`; keep `audio_fade_style` crossfade; set stinger transition `volume` so whoosh sits under voice/Desktop (calibrate on reimport).
- Regenerate with whoosh if asset ever loses audio:  
  `python tools/generate_stinger.py --profile marcato --with-whoosh`

### Non-goals

- Independent audio fade longer than video duration.
- Fading global devices that are not scene sources (Desktop is already a scene/collection source pattern to preserve).

## Verification

- [ ] Starting Soon → Lobby: 900 ms Dissolvenza; bed A fades out, bed B fades in (no click/cut).
- [ ] Lobby → Live: Stinger + whoosh; Lobby bed fades out; Desktop (+ mic) fades in.
- [ ] Live → BRB: Dissolvenza; Desktop/mic out, BRB bed in.
- [ ] BRB → Ending: Stinger + whoosh; Ending bed in.
- [ ] Taglio quick transition still hard-cuts when selected.
- [ ] VirtualDeck / Session Director scene switches use the same collection defaults/overrides (no special path required).

## Risks

- OBS JSON field for per-scene transition override must match OBS 32.x export shape — discover from a hand-set override export if generator shape is wrong.
- Monitoring (“Monitor only”) may not mirror stream crossfade; judge from recording/stream, not headphones alone.
