# Session Director (Live ↔ Lobby + flags)

Hands-free OBS direction for **S.Marcato 42** slim live:

| Condition | Scene |
|-----------|--------|
| Telemetry connected (iRacing session) | **Live** |
| iRacing process up, telemetry stale/down | **Lobby** |
| Flag yellow / red / checkered | **Flag *** |
| Green / none after a flag | stacked home (`Live` or `Lobby`) |
| Starting Soon / BRB / Ending | **never** auto-left (VirtualDeck / manual) |

Built on P3-04 Flag Director. Entry point unchanged: `Start-FlagDirector.bat` → `adapters/obs_flag_director/director.py`.

Design: [`docs/superpowers/specs/2026-08-14-marcato-session-director-design.md`](superpowers/specs/2026-08-14-marcato-session-director-design.md).  
VirtualDeck: [`OBS_VIRTUALDECK.md`](OBS_VIRTUALDECK.md). Flag-only notes: [`FLAG_DIRECTOR.md`](FLAG_DIRECTOR.md).

## Prerequisites

1. OBS Studio **28+** with **WebSocket** enabled (`:4455`) — [`OBS_VIRTUALDECK.md`](OBS_VIRTUALDECK.md)
2. Reimport **S.Marcato 42** after `python tools/generate_pack.py --profile marcato`
3. Config server `:8766` (telecronaca Browser Sources are HTTP)
4. Python deps:

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
| `liveScene` / `lobbyScene` / `homeScene` | Default `Live` / `Lobby` / `Live` |
| `sessionDebounceMs` | Live↔Lobby debounce (default 4000) |
| `autoStartTelemetry` | Start `Start-Telemetry.bat iracing` when iRacing is up |
| `iracingProcessNames` | Process watch list |
| `manualScenes` | Scenes the director will not auto-leave |
| `scenes.*` | Flag scene names |

## Run

```powershell
.\Start-Telecronaca.bat iracing
# or:
.\Start-FlagDirector.bat
python adapters\obs_flag_director\director.py --dry-run
```

## Mixer notes (P3-05 snippet)

| Source | Role |
|--------|------|
| Audio Desktop | Race / system (center monitor gameplay) |
| Microfono | Focusrite 2i2 (or `MARCATO_MIC_ID` / `obs/mic.device.json`) |
| Music Starting Soon / Lobby / BRB / Ending | Royalty-free synthesized beds — active only on those scenes |

On **Live**, music beds are not in the scene (Desktop + Mic only).

## Tests

```powershell
python -m pytest tests/test_flag_director.py -v
```

## Verification checklist

- [ ] WebSocket enabled → VirtualDeck lists slim scenes
- [ ] iRacing closed → no spurious cuts while on Starting Soon
- [ ] iRacing UI only → Lobby + music within debounce
- [ ] Session with telemetry → Live + Monitor Centro + Broadcast Chrome
- [ ] Flag yellow → Flag Yellow → green → Live
- [ ] Exit to UI (telem loss) → Lobby
- [ ] Mic meters = Focusrite; Desktop carries race audio
