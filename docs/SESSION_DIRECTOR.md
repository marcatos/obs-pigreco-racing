# Session Director (Live ↔ Lobby + flags)

Hands-free OBS direction for **S.Marcato 42** slim live:

| Condition | Scene / action |
|-----------|----------------|
| Telemetry connected (iRacing session) | restore **Live** or **Headcam** (last race scene); never yank Headcam→Live |
| iRacing process up, telemetry stale/down | **Lobby** |
| iRacing fully closed | **Lobby** (also from Headcam) |
| Flag yellow / red / checkered | **Overlay FX on Live** (default `flagPresentation=overlay`) — no cutaway |
| Starting Soon / BRB / Ending | **never** auto-left (VirtualDeck / manual) |

Built on P3-04 Flag Director. Entry: `Start-FlagDirector.bat` → `adapters/obs_flag_director/director.py`.

Design: [`docs/superpowers/specs/2026-08-14-marcato-session-director-design.md`](superpowers/specs/2026-08-14-marcato-session-director-design.md).  
VirtualDeck: [`OBS_VIRTUALDECK.md`](OBS_VIRTUALDECK.md). Flag FX: [`FLAG_DIRECTOR.md`](FLAG_DIRECTOR.md).

## Prerequisites

1. OBS Studio **28+** with **WebSocket** enabled (`:4455`) — [`OBS_VIRTUALDECK.md`](OBS_VIRTUALDECK.md)
2. Reimport **S.Marcato 42** after `python tools/generate_pack.py --profile marcato`
3. Config server `:8766` (telecronaca + Flag FX Browser Sources are HTTP) — Lua autostart
4. Session Director + telemetry — same Lua script on OBS open (`ensure_session_director`)
5. Python deps:

```powershell
pip install -r adapters/obs_flag_director/requirements.txt
```

## Config

`Start-FlagDirector.bat` creates `config.local.json` from the example on first run.

Edit `adapters/obs_flag_director/config.local.json`:

| Key | Meaning |
|-----|---------|
| `obsPassword` | OBS websocket password (**never commit**) |
| `dryRun` | `true` = log only; `false` = real switches |
| `flagPresentation` | `overlay` (default) or `scenes` |
| `liveScene` / `lobbyScene` / `homeScene` | Default `Live` / `Lobby` / `Live` |
| `raceScenes` | Scenes to resume after Lobby (default `Live`, `Headcam`) |
| `sessionDebounceMs` | Live↔Lobby debounce (default 4000) |
| `autoStartTelemetry` | Start `Start-Telemetry.bat iracing` when iRacing is up |
| `iracingProcessNames` | Process watch list |
| `manualScenes` | Scenes the director will not auto-leave |
| `scenes.*` | Flag scene names (only if `flagPresentation=scenes`) |

If you already have a `config.local.json`, set `"flagPresentation": "overlay"` so the director stops cutting to missing Flag * panels.

## Run

OBS opens → Lua `pigreco_config_autostart.lua` starts **Session Director + telemetry** silently (same path as the config server). Manual fallback:

```powershell
.\Start-Telecronaca.bat iracing
# or:
.\Start-FlagDirector.bat
python adapters\obs_flag_director\director.py --dry-run
```

Idempotent ensure (no console):

```powershell
python tools\ensure_session_director.py
# or:
wscript //nologo tools\ensure_session_director_silent.vbs
```

## Mixer notes (P3-05 snippet)

| Source | Role |
|--------|------|
| Audio Desktop | Race / system (center monitor gameplay) |
| Microfono | Focusrite 2i2 (or `MARCATO_MIC_ID` / `obs/mic.device.json`) |
| Music Starting Soon / Lobby / BRB / Ending | Royalty-free beds (~−14 dB file gain + mixer ~0.15–0.18) — active only on those scenes |

On **Live**, music beds are not in the scene (Desktop + Mic only).

## Scene transitions (Move)

Collection default: **S.Marcato Move** (~650 ms) for all scene pairs (no per-scene stinger overrides). Details: [`TRANSITIONS.md`](TRANSITIONS.md).

Verify from **stream/recording**:

- [ ] Starting Soon → Lobby: Move morph (~650 ms).
- [ ] Lobby → Live: Move; Lobby bed out; Desktop (+ mic) in.
- [ ] Live → BRB: Move; Desktop/mic out, BRB bed in.
- [ ] BRB → Ending: Move; Ending bed in.

## Instant Replay (P2-04)

On hot telemetry moments (`incident`, `loss_of_control`, `near_miss`, `hard_overtake`) the Session Director:

1. Saves the OBS **Replay Buffer**
2. Loads the clip into **Instant Replay Clip**
3. Shows the nested **Instant Replay** source (960×540, bottom-right) on the current race scene (`Live` / `Headcam`)
4. Hides it after `maxPlayMs` (default 10 s)

**Prerequisites**

- OBS → Settings → Output → Replay Buffer **enabled** (20–30 s recommended)
- Collection regenerated with Instant Replay sources (`python tools/generate_pack.py --profile marcato`)
- `instantReplay.enabled` in `adapters/obs_flag_director/config.local.json` (see `config.example.json`)

Cooldown default: 50 s between auto replays. Manual scene stays on Live/Headcam (no scene switch).

## Session reset

Select **Reset Session** in VirtualDeck to clear telemetry continuity, broadcast overlays, and replay/director state without restarting OBS or Python. The empty auxiliary scene is only a command trigger; Session Director restores the previous **Live** or **Headcam** scene automatically.

Program never stays on the empty scene: with no known previous scene the director falls back to the preferred home (**Live** when telemetry is up, else **Lobby**), and a failed scene switch is retried on the next poll instead of latching. See the [session reset design](superpowers/specs/2026-08-20-session-reset-design.md).

## Tests

```powershell
python -m pytest tests/test_flag_director.py tests/test_instant_replay_policy.py -v
```

## Verification checklist

- [ ] No flashing cmd/PowerShell windows while Session Director runs (tasklist/netstat are hidden)
- [ ] WebSocket enabled → VirtualDeck lists slim scenes
- [ ] iRacing closed → no spurious cuts while on Starting Soon
- [ ] iRacing UI only → Lobby + music within debounce
- [ ] Session with telemetry → Live + Monitor Centro + Broadcast Chrome
- [ ] Yellow/red/checkered → animated rails/badge on Live; gameplay + HUD visible
- [ ] Green → FX clears; stay on Live
- [ ] Exit to UI (telem loss) → Lobby
- [ ] Mic meters = Focusrite; Desktop carries race audio
