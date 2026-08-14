# Flag Director (P3-04)

> Prefer **[`SESSION_DIRECTOR.md`](SESSION_DIRECTOR.md)** for live Marcato (Live↔Lobby + flags). This page keeps the flag-cut behaviour reference.

Hands-free race direction for OBS: when telemetry reports **yellow**, **red**, or **checkered**, the director cuts to branded flag scenes and returns to your previous live scene on **green**. Overlay banners (P3-06) stay independent of scene cuts.

Pack scenes (after `python tools/generate_pack.py --profile marcato`):

| Scene | Source |
|-------|--------|
| `Flag Yellow` | `flag-scene.html?flag=yellow` |
| `Flag Red` | `flag-scene.html?flag=red` |
| `Flag Checkered` | `flag-scene.html?flag=checkered` |

Default home for **S.Marcato 42** slim live: **`Live`**. Replay / Rec 2K still use `Rec Singolo Live` if you point `homeScene` there.

## Prerequisites

1. Telemetry running: `Start-Telemetry.bat mock` or `iracing` (or `Start-Telecronaca.bat`)
2. Config server on `:8766` (flag HTML is served over HTTP)
3. OBS Studio **28+** with **WebSocket server** enabled — see [`OBS_VIRTUALDECK.md`](OBS_VIRTUALDECK.md)
4. Reimport the collection that contains Flag * scenes
5. Python deps:

```powershell
pip install -r adapters/obs_flag_director/requirements.txt
```

## Config

`Start-FlagDirector.bat` creates `config.local.json` from the example on first run.

Edit `adapters/obs_flag_director/config.local.json`:

- `obsPassword` — OBS websocket password (**never commit**)
- `dryRun`: start `true` (logs only); set `false` for real switches
- `homeScene` / `liveScene` / `lobbyScene` — see Session Director
- `scenes.*` — must match OBS scene names exactly

## Run

```powershell
.\Start-Telecronaca.bat mock
# or separately:
.\Start-FlagDirector.bat
python adapters\obs_flag_director\director.py --dry-run
```

## Behaviour

| Flag | Action |
|------|--------|
| yellow / red / checkered | Switch to mapped scene |
| green / none | Return to stacked home (or `homeScene`) |
| blue / white / … | No scene change (v1) |

Debounce default **1500 ms**. Overlay chrome is unchanged.

## Tests

```powershell
python -m pytest tests/test_flag_director.py -v
```
