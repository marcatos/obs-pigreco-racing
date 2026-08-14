# Flag Director (P3-04)

Switches OBS program scenes when iRacing / mock telemetry reports **yellow**, **red**, or **checkered**. Returns to the previous live scene on **green**. Broadcast overlay banners stay independent (P3-06).

## Prerequisites

1. Telemetry running: `Start-Telemetry.bat mock` or `iracing`
2. OBS Studio **28+** with **WebSocket server** enabled  
   Tools → WebSocket Server Settings → Enable → note port (default `4455`) and password
3. Create three scenes (names must match config), e.g.  
   - `Flag Yellow`  
   - `Flag Red`  
   - `Flag Checkered`  
   Put a full-frame graphic / color source on each if you want a full-screen flag look.
4. Python deps:

```powershell
pip install -r adapters/obs_flag_director/requirements.txt
```

## Config

```powershell
copy adapters\obs_flag_director\config.example.json adapters\obs_flag_director\config.local.json
```

Edit `config.local.json`:

- `obsPassword` — OBS websocket password (never commit this file)
- `dryRun`: `true` logs only; set `false` for real switches
- `homeScene` — fallback if the director never saw a non-flag scene (e.g. `Rec * Live` or `Live Race`)
- `scenes.yellow|red|checkered` — exact OBS scene names

`config.local.json` is gitignored.

## Run

```powershell
.\Start-FlagDirector.bat
# or
python adapters\obs_flag_director\director.py --dry-run
python adapters\obs_flag_director\director.py
```

Keep the window open while streaming. Restart after changing config.

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
