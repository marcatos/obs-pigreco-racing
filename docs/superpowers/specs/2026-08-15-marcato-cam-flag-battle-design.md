# Design: Marcato cam fix + flag strip + battle gating

**Date:** 2026-08-15  
**Status:** approved (design dialogue)  
**Roadmap:** P3-12 (new) — flag strip + battle session gate; P1-04 follow-up — cam device IDs  
**Related:** ADR-005, P3-09 field ticker, P3-10 battle panel, `docs/CAMERAS.md`, `docs/TELEMETRY_BROADCAST.md`

## Problem

1. **Cams:** On S.Marcato OBS collections, nested `Cam PIP` / `Cam 2 PIP` show frames (carbon + CAM chrome) but no live video — StreamCam `video_device_id` in the generator uses broken `#22` escaping / stale instance path vs devices currently on the PC.
2. **Flags:** Checkered (and related) stay on the broadcast chrome as long as the SDK flag is set; white/debris are weak or mis-mapped. User wants a less invasive, FIELD-ticker-like top strip with a fixed 10s presentation for checkered / last lap / debris.
3. **Battle:** The bottom battle pack can arm before the race is live (formation / pre-start). It must only arm from race lap 1 (not formation), may arm in practice with others, and must stay off in quali (including solo).

## Goals

- Wire **Logitech StreamCam** → Cam PIP (face, bottom-left) and **USB Camera** → Cam 2 PIP (seat, bottom-right) using live DirectShow IDs; regenerate Marcato scene JSON (and shared PiGreco IDs if the same constants are used).
- Replace the thin top flag banner + flag moment chips with a **top full-width strip** using FIELD ticker choreography: rise → expand L→R → hold 10s → collapse → drop.
- Map `white` → LAST LAP, `debris` → DEBRIS (red/yellow stripes), `checkered` → CHECKERED; each timed to **10s** even if the SDK flag remains.
- Correct iRacing `SessionFlags` bit mapping so debris is distinct from blue.
- Gate battle panel: **race** only when live (same readiness idea as `race_live_order_ready`); **practice** when other cars exist and gaps meet existing thresholds; **quali / cooldown / unknown** always off.

## Non-goals

- Full chrome redesign (session strip, leaderboard, focus, accents) beyond what the new flag strip replaces.
- Moving cams out of nested PiP scenes.
- Using NVIDIA Broadcast / OBS Virtual Camera as the primary dshow sources.
- Changing battle gap/tick/sensitivity math — only eligibility by session.
- Flag Director scene cutaways (`flagPresentation=scenes`) behavior changes (overlay strip is independent).

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Approach | Targeted pack fix (approach 1) |
| Flag UI | Top strip, FIELD-like expand L→R (option B) |
| Flag timing | Checkered, white, debris: **10s then hide** (option B for those three) |
| Yellow / red | Stay **while active** (safety); use the same strip visual language, no forced 10s cut |
| Battle sessions | Race from lap 1 + practice with others; never quali (option B) |
| Cam architecture | Keep nested Cam PIP / Cam 2 PIP; refresh device IDs only |
| Roadmap ID | **P3-12** for strip + battle gate; note P1-04 cam ID fix in ROADMAP notes |

## Architecture

```
PC DirectShow devices
  StreamCam ──► generate_pack STREAMCAM_ID ──► Cam PIP nest ──► Live scenes
  USB Camera ──► generate_pack USBCAM_ID   ──► Cam 2 PIP nest ─┘

iRacing SessionFlags ──► iracing_bridge._flag_name ──► tick.flag
                              ↓
                    overlays/broadcast.js
                      ├─ flag strip (top, 10s for white/debris/checkered)
                      └─ updateFightPanel (session gate before arm)
```

### Cam device IDs (as of design date)

Detected via ffmpeg dshow on the authoring PC:

| Role | Friendly name | Path fragment |
|------|---------------|---------------|
| Face (Cam PIP) | Logitech StreamCam | `usb#vid_046d&pid_0893&mi_00#8&33ee287c&0&0000#{65e8773d-…}` |
| Seat (Cam 2 PIP) | USB Camera | `usb#vid_0c6a&pid_646a&mi_00#9&1779791d&0&0000#{65e8773d-…}` |

OBS `video_device_id` format (no broken `#22` escaping):

`{FriendlyName}:\\?\usb#vid_…&pid_…&mi_00#{instance}#{guid}\global`

After regen: close OBS → import/reopen collection → verify eyes on Cam PIP / Cam 2 PIP. If a feed is still black, re-pick device in nested scene Properties (document in `CAMERAS.md`).

### Flag strip

- New DOM under broadcast chrome (top edge), visual sibling of `.bc-ticker` but top-anchored.
- Choreography mirrors field ticker phases: enter (rise) → expand L→R → show → collapse → drop.
- Hold duration: **10000 ms** for `checkered` | `white` | `debris`.
- Label mapping: `LAST LAP` / `DEBRIS` / `CHECKERED` (and yellow/red labels while held).
- Debris CSS: red/yellow repeating stripes (`data-flag="debris"`).
- On new flag while strip is showing: replace content and **reset** the 10s timer (for timed flags).
- Remove/disable: `.bc-flag-banner` usage for these flags; do not enqueue flag moment chips for white/debris/checkered (yellow/red optional: strip only, no large moment chip).
- Config (optional): `broadcastFlagStripMs` default 10000 — sync `config.example.js`.

### SessionFlags correction (`iracing_bridge.py`)

Align with irsdk:

| Name | Bit |
|------|-----|
| checkered | `0x00000001` |
| white | `0x00000002` |
| green | `0x00000004` |
| yellow | `0x00000008` |
| red | `0x00000010` |
| blue | `0x00000020` |
| **debris** | `0x00000040` |
| black | `0x00010000` |
| meatball (repair) | `0x00100000` |

Priority in `_flag_name`: checkered > red > yellow > debris > white > blue > black > meatball > green (debris before white so debris+white edge cases prefer debris if both set; adjust only if live telemetry proves otherwise).

CONTRACT `flag` enum gains `debris`.

### Battle gating

In `updateFightPanel` (and any battle hero arm path that mirrors it):

1. If `tick.session === "quali"` or `cooldown` or `unknown` → force panel off, clear streaks.
2. If `session === "practice"` → allow existing gap logic only if standings/relative imply **≥1 other car** (not solo).
3. If `session === "race"` → allow only when live-order ready equivalent:
   - Prefer client fields already on the tick (`lap` of focus ≥ 1 and session not pre-race), **or**
   - Emit `battleEligible: bool` from the bridge using `race_live_order_ready` if client signals are insufficient for formation/pace.
4. Default implementation order: try client-side gate first; add `battleEligible` only if formation still false-triggers.

## Components / files

| File | Change |
|------|--------|
| `tools/generate_pack.py` | Fix `STREAMCAM_ID` / confirm `USBCAM_ID`; regen collections |
| `obs/S_Marcato_*.json` (+ PiGreco if shared) | Regenerated |
| `overlays/broadcast-chrome.html` | Flag strip markup |
| `overlays/broadcast.js` | Strip controller + battle gate; stop flag banner/chips as above |
| `overlays/assets/broadcast.css` | Strip styles + debris; retire/ignore old banner for timed flags |
| `overlays-marcato/*` | Twin markup/CSS/JS only if not already sharing `../overlays` |
| `adapters/telemetry/iracing_bridge.py` | Flag bits + debris |
| `adapters/telemetry/CONTRACT.md` | Document `debris` |
| `overlays/config.example.js` | Optional `broadcastFlagStripMs` |
| `docs/CAMERAS.md` | Device refresh + verify steps |
| `docs/TELEMETRY_BROADCAST.md` | Strip + battle session rules |
| `docs/ROADMAP.md` | Add P3-12; note P1-04 cam ID follow-up |
| `tests/` | Flag bit/debris; battle gate matrix; strip timer if testable |

## Error handling

- Cam: wrong/missing device → empty PiP with carbon/frame (current failure mode); docs say re-pick in OBS. Generator logs the IDs written at regen time.
- Flag strip: missing WS / `telemetryEnabled: false` → strip stays off.
- Battle: missing session field → treat as ineligible (fail closed).

## Testing

- Unit: `_flag_name` debris/blue/black/meatball bits; battle gate table (race lap0 off, race lap1 on, practice multi on, practice solo off, quali off).
- Manual OBS: after regen, both PiP nests show video; eyes still independent.
- Manual overlay (mock WS): white / debris / checkered each show strip ~10s then drop; yellow holds until green; battle does not flash pre-green.

## Acceptance

- [ ] StreamCam and USB Camera visible on Cam PIP / Cam 2 PIP after regen + OBS reopen
- [ ] Top flag strip uses FIELD-like L→R expand; checkered/white/debris clear after ~10s
- [ ] Debris shows red/yellow treatment; white labeled LAST LAP
- [ ] Battle off in formation/pre-race and all quali; on in practice with others and race from lap 1
- [ ] CONTRACT + docs + config.example updated; ROADMAP P3-12 claimed/done when shipped
- [ ] Conventional Commits for implementation

## Open follow-ups (out of this spec)

- Broader “less invasive” chrome pass (session accents, smaller battle card) — deferred
- Auto-discover dshow IDs in Setup.ps1 — later nicety
