# Design system — PiGreco Racing stream

## Brand source of truth

Official site tokens (`pigrecoracing.com` / `pigreco-restyle.css`):

| Token | Value | Use |
|-------|-------|-----|
| `--pgr-green` | `#00C400` | Primary accent, π, success, live |
| `--pgr-blue` | `#009FE5` | Secondary accent, links, labels |
| `--pgr-black` | `#050505` | Deep blacks |
| `--pgr-bg` | `#080A0C` | Page / panel base |
| `--pgr-panel` | `#11161A` | Cards / chrome |
| `--pgr-text` | `#F7FAFC` | Primary text |
| `--pgr-muted` | `#A7B1BA` | Secondary text |

Logos: green π mark + white wordmark (transparent PNG in `overlays/assets/`).

## Typography

- Display: Orbitron (headlines, labels)
- Body: Rajdhani
- Avoid Inter / Roboto / Arial as primary stream fonts

## Motion

- Prefer 2–3 intentional motions per surface (fade sponsor, pulse logo, countdown tick).
- No purple glow stacks, no emoji storms, no pill clusters in the hero/live center.
- Sponsor / telemetry must stay **peripheral** (corners); never cover center FOV.

## Layout (1920×1080 live)

| Zone | Content |
|------|---------|
| Top-left | Sponsor rotator / session badge |
| Top-right | Team watermark + handle |
| Bottom-left | Webcam + frame |
| Bottom-left+ | Lower-third (right of cam) |
| Center | Gameplay only |

## Tone

Professional sim team, ironico ma pulito. Italian UI copy default; config may override.

## Do / Don’t

- DO reuse `theme.css` variables for new widgets.  
- DO keep interstitial scenes (Starting/BRB/Ending) full-bleed brand panels.  
- DON’T introduce a second unrelated color system.  
- DON’T add dense dashboards to the first live viewport.
