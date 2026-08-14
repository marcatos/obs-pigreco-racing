# Flag Director (P3-04)

> Prefer **[`SESSION_DIRECTOR.md`](SESSION_DIRECTOR.md)** for live Marcato (Live↔Lobby + flags).

Default UX: **transparent animated Flag FX** on the Live (or Replay Live) Browser Source. Gameplay + telecronaca stay visible; no full-screen color panels.

| Mode (`flagPresentation`) | Behaviour |
|---------------------------|-----------|
| `overlay` (**default**) | No OBS scene cut. `Overlay Flag FX` listens to telemetry WS. |
| `scenes` | Optional cut to Flag * aux scenes (still built with gameplay + chrome underneath). |

## Live pack (S.Marcato 42)

Scene **Live** includes `Overlay Flag FX` → `flag-scene.html` (transparent). Yellow / red / checkered animate rails + badge; center FOV stays clear.

## Replay / Rec 2K

- Live-like scenes also carry `Overlay Flag FX` (telemetry-driven).
- Optional **Flag Yellow / Red / Checkered** aux scenes = same layout as Rec Singolo Live + forced `?flag=…` FX (for VirtualDeck / `flagPresentation=scenes`).

## Prerequisites

1. Telemetry: `Start-Telemetry.bat` / `Start-Telecronaca.bat`
2. Config server `:8766` (HTTP Browser Sources)
3. OBS WebSocket — [`OBS_VIRTUALDECK.md`](OBS_VIRTUALDECK.md)
4. `python tools/generate_pack.py --profile marcato` (reinstall collections)

## Config

`adapters/obs_flag_director/config.local.json`:

- `flagPresentation`: `overlay` (default) or `scenes`
- `obsPassword`, `dryRun`, `homeScene` / `liveScene` / `lobbyScene`
- `scenes.*` — only used when `flagPresentation=scenes`

## Behaviour

| Flag | `overlay` | `scenes` |
|------|-----------|----------|
| yellow / red / checkered | FX on current Live | Switch to mapped Flag * |
| green / none | FX off | Return to stacked home |
| blue / white / … | No change | No change |

Debounce default **1500 ms**.

## Tests

```powershell
python -m pytest tests/test_flag_director.py -v
```
