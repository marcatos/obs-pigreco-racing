# OBS PiGreco Racing

**Production-ready OBS Studio pack for sim racing streams** — brand-coherent chrome, local HTML overlays, and a double-click Windows setup. One repo, two looks: team **PiGreco Racing** and personal **S.Marcato 42**.

![Windows](https://img.shields.io/badge/Windows-first-0078D4?style=flat-square&logo=windows&logoColor=white)
![OBS](https://img.shields.io/badge/OBS-32.x-302E31?style=flat-square)
![Canvas](https://img.shields.io/badge/Canvas-1920%C3%971080-00C400?style=flat-square)
![Local-first](https://img.shields.io/badge/Local--first-no%20cloud-009FE5?style=flat-square)
![Profiles](https://img.shields.io/badge/Profiles-2-080A0C?style=flat-square)

> **Pilota non tecnico?** Apri [`LEGGIMI.txt`](LEGGIMI.txt) oppure fai doppio clic su **`Setup.bat`** — guida e setup restano in italiano.

Zip → useful OBS preview in under **10 minutes**. Gameplay stays center-stage; sponsors and telemetry stay peripheral. No SaaS, no mandatory cloud — files on disk you can share in Discord.

---

## Showcase

Full-bleed **1920×1080** previews — browse locally: [`showcase/index.html`](showcase/index.html).

### S.Marcato 42

| Starting Soon | Live Triplo |
|:---:|:---:|
| ![Starting Soon](showcase/marcato-01-starting-soon.png) | ![Live Triplo](showcase/marcato-05-triple-frame.png) |

| BRB | Ending |
|:---:|:---:|
| ![BRB](showcase/marcato-03-brb.png) | ![Ending](showcase/marcato-04-ending.png) |

<p align="center">
  <img src="showcase/marcato-02-live-chrome.png" alt="Live Chrome" width="720" />
  <br />
  <sub>Live Chrome — lower-third + CAM</sub>
</p>

### PiGreco Racing

| Starting Soon | Live |
|:---:|:---:|
| ![PiGreco Starting Soon](showcase/01-starting-soon.png) | ![PiGreco Live](showcase/02-live-chrome.png) |

| BRB | Ending |
|:---:|:---:|
| ![PiGreco BRB](showcase/03-brb.png) | ![PiGreco Ending](showcase/04-ending.png) |

```powershell
python tools/generate_showcase.py
```

---

## Why this pack

- **Setup.bat** — nick, optional Python install (UAC), overlays personalized, scene collection copied into OBS AppData
- **Brand chrome that respects the FOV** — π / 42 identity in corners; center stays gameplay
- **Browser Source overlays** — HTML/CSS/JS, not baked OBS images; refresh when you change config
- **Original interstitial music** — synthesized locally (typical Twitch Content ID from stock libraries avoided)
- **Optional sim-pro stack** — iRacing telecronaca, track map, auto flag scenes — all local WebSocket / HTTP

Canvas target: **1920×1080** @ 60 fps (OBS 32.x, relative transforms `pos_rel` / `scale_rel`).

---

## Two profiles

| Profile | Brand | Overlays | OBS collections |
|---------|--------|----------|-----------------|
| **PiGreco Racing** | Team `#00C400` / `#009FE5` | `overlays/` | `obs/PiGreco_Racing.json` |
| **S.Marcato 42** | Carbon / ice / Rosso Corsa `#E10600` | `overlays-marcato/` | `obs/S_Marcato_42.json`, `obs/S_Marcato_Replay.json`, `obs/S_Marcato_Rec_2K.json` |

Switch collections in OBS — no uninstall needed.

---

## Features

| Area | What you get | Docs |
|------|----------------|------|
| Broadcast polish | Countdown, session badge, BRB timer, rich ending + QR | [`docs/`](docs/README.md) |
| Stinger & cams | Brand stinger, Cam PIP / Cam 2, greenscreen notes | [`STINGER`](docs/STINGER.md) · [`CAMERAS`](docs/CAMERAS.md) |
| Config dock | Live config at `http://127.0.0.1:8766/` | [`OBS_CONFIG_PANEL`](docs/OBS_CONFIG_PANEL.md) |
| Telecronaca | Standings / focus / flags over WebSocket `:8765` | [`TELEMETRY_BROADCAST`](docs/TELEMETRY_BROADCAST.md) |
| Track map | Peripheral minimap + self-learn outlines | [`TRACK_MAP`](docs/TRACK_MAP.md) |
| Flag director | Auto scene on yellow / red / checkered | [`FLAG_DIRECTOR`](docs/FLAG_DIRECTOR.md) |
| Rec 2K | Native 2560×1440 VOD profile | [`ADR-007`](docs/adr/007-recording-1440p.md) |
| Engagement | StreamElements chat / alert themes | [`adapters/streamelements`](adapters/streamelements/README.md) |

Also included: Game Capture (iRacing) + Display Capture, StreamCam PIP, Move transitions, clean **Rec** layouts, **Replay** pack for commentary streams.

---

## Quick start (Windows)

### 1. Setup

```text
double-click → Setup.bat
```

Prompts for nick / pilot name, installs Python if missing, writes overlay config, copies the collection to:

`%APPDATA%\obs-studio\basic\scenes\`

Italian walkthrough: [`LEGGIMI.txt`](LEGGIMI.txt) · PDF: [`Guida_PiGreco_OBS.pdf`](Guida_PiGreco_OBS.pdf)

### 2. Open OBS

**Scene Collection** → pick:

- **PiGreco Racing** — team stream
- **S.Marcato 42** — personal live race
- **S.Marcato Replay** — iRacing replay commentary

### 3. Config panel (recommended)

On OBS open, Lua `obs/scripts/pigreco_config_autostart.lua` starts the dock server at `http://127.0.0.1:8766/`. Optional login keepalive: `tools/install_config_autostart.ps1`.

1. **View → Docks → Custom Browser Docks**:
   - PiGreco: `http://127.0.0.1:8766/`
   - Marcato: `http://127.0.0.1:8766/?profile=marcato`
2. Fallback: double-click `Start-ConfigPanel.bat`
3. Telecronaca (optional): `Start-Telecronaca.bat mock` (or `iracing`) — or `Start-Telemetry.bat` + `Start-FlagDirector.bat`

### 4. After overlay edits

Browser Source → **Refresh cache of current page** (or restart OBS).

> Close OBS before regenerating JSON under `obs/`, or OBS may overwrite files on exit.

---

## Scenes

### S.Marcato 42 (live)

| Scene | Use |
|-------|-----|
| Starting Soon | Countdown / teaser + music bed |
| Live Race / Singolo / Triplo | Center monitor, single, or iRacing window + chrome + cam |
| Rec * / Rec * Live | Clean recording or stream alias of Live layouts |
| BRB / Ending | Pause and close |

Guide: [`docs/S_MARCATO_42.md`](docs/S_MARCATO_42.md)

### S.Marcato Replay

| Scene | Use |
|-------|-----|
| Replay iRacing / Monitor | Game or center monitor + REPLAY badge + Cam PIP |
| Rec * / Rec * Live | Clean VOD or commented stream (+ broadcast chrome eye-off by default) |
| BRB / Ending | Pause and close |

Notes: [`replays/LEGGIMI.txt`](replays/LEGGIMI.txt) · Broadcast chrome → `ws://127.0.0.1:8765`

### Recording 2K (2560×1440)

1. OBS **Profile** → `Rec 2K` · **Collection** → `S.Marcato Rec 2K`
2. `Rec Singolo Live` / `Rec Triplo Live` (or clean Rec without overlays)
3. Encoder tip: **NVENC HEVC VBR ~25 Mbps** (max 40) for 1440p60 VODs
4. Stream stays on 1080 + Live/Replay collections

Template: `obs/profiles/Rec_2K/` · [`ADR-007`](docs/adr/007-recording-1440p.md)

### PiGreco Racing

Starting Soon · Live Race · Live Singolo · Rec… · BRB · Ending  
PDF: [`Guida_PiGreco_OBS.pdf`](Guida_PiGreco_OBS.pdf)

---

## Streamer config

**PiGreco** — `overlays/config.js` (or the dock): `username` / `pilotName` / `twitchHandle`, `teamName` / `eventTitle` / `tagline`, `sponsors` / `sponsorsEnabled`.

**Marcato** — `overlays-marcato/config.values.json` (same ideas, no team sponsors). Query overrides, e.g. `live-chrome.html?eventTitle=Night%20Race`.

---

## Docs map

Full index: **[`docs/README.md`](docs/README.md)**

| For… | Start here |
|------|------------|
| Non-technical pilots (IT) | [`LEGGIMI.txt`](LEGGIMI.txt) · [`Guida_PiGreco_OBS.pdf`](Guida_PiGreco_OBS.pdf) |
| On-stream polish | [`DESIGN_SYSTEM`](docs/DESIGN_SYSTEM.md) · [`STINGER`](docs/STINGER.md) · [`CAMERAS`](docs/CAMERAS.md) |
| Sim pro | [`TELEMETRY_BROADCAST`](docs/TELEMETRY_BROADCAST.md) · [`TRACK_MAP`](docs/TRACK_MAP.md) · [`FLAG_DIRECTOR`](docs/FLAG_DIRECTOR.md) |
| Contributors / agents | [`AGENTS.md`](AGENTS.md) · [`STRATEGY.md`](STRATEGY.md) · [`ROADMAP`](docs/ROADMAP.md) · [`ARCHITECTURE`](docs/ARCHITECTURE.md) |

---

## Repo layout

```text
Setup.bat / Setup.ps1     Guided Windows setup
LEGGIMI.txt               Italian quick start
obs/                      Scene collection JSON
overlays/                 PiGreco pack
overlays-marcato/         S.Marcato 42 pack
audio/interstitials/      Generated music beds
replays/                  Replay notes + media slot
tools/                    Generators and setup
docs/                     Architecture, roadmap, guides
adapters/                 Telemetry, flags, StreamElements
showcase/                 PNG previews
tests/                    Pytest
```

---

## Developers & agents

```powershell
# Regenerate OBS collections (close OBS first)
python tools/generate_pack.py --profile pigreco
python tools/generate_pack.py --profile marcato

# Original music beds (anti Content ID)
python tools/generate_interstitial_music.py

# Showcase / PDF guide
python tools/generate_showcase.py
python tools/generate_pdf_guide.py

# Tests
python -m pytest -q
```

Agent rules: [`AGENTS.md`](AGENTS.md) · product strategy: [`STRATEGY.md`](STRATEGY.md) · execution IDs: [`docs/ROADMAP.md`](docs/ROADMAP.md)

### Typical capture

- Triple **separate** monitors (not Surround): classic live often uses the **center**; **Live Triplo** captures the **iRacing window** (in-game triple span if enabled)
- Webcam: Logitech StreamCam ID is wired in the pack — change if you use another device
- Multistream: Restream / OBS multistream plugins (outside this repo)

### Example hotkeys

| Key | Scene |
|-----|--------|
| F1 | Starting Soon |
| F2 | Live Race / Replay iRacing |
| F3 | Live Singolo / Live Triplo |
| F4 | BRB |
| F5 | Ending |

---

## Attribution & support

- **PiGreco Racing** brand assets — see [`ATTRIBUTION.md`](ATTRIBUTION.md)
- **S.Marcato 42** — pilot brand kit under `overlays-marcato/assets/brand/`
- Music beds — generated by `tools/generate_interstitial_music.py` (original to this pack)

**Do not commit** stream keys, OAuth tokens, StreamElements JWTs, or secret URLs.

Issues and PRs welcome on this repository. Non-technical team path remains **`Setup.bat` → OBS → Refresh overlay**.
