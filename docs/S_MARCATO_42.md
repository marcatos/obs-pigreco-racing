# S.Marcato 42 — overlay pack personale

Pacchetto broadcast **personale** per il pilota **S.Marcato** (auto **42**): tema carbon/acciaio in `overlays-marcato/`, collezione OBS **S.Marcato 42**. Nessun branding PiGreco, nessuno sponsor rotator.

Il pack **PiGreco Racing** resta installato nello stesso repo: puoi alternare le due collezioni in OBS senza disinstallare nulla.

## Setup rapido (collezione OBS)

### 1. Chiudi OBS

Prima di rigenerare o importare la collezione, **chiudi completamente OBS** (anche dalla tray). Evita di sovrascrivere JSON mentre OBS tiene i file aperti.

### 2. Genera la collezione sul tuo PC

I Browser Source nel JSON usano percorsi `file:///` locali. Esegui dal repo (Python come per `Setup.bat`):

```powershell
python tools/generate_pack.py --profile marcato
```

Output atteso: `obs/S_Marcato_42.json` (nome collezione **S.Marcato 42**, URL verso `overlays-marcato/*.html`).

Dopo aver modificato `overlays-marcato/config.values.json` a mano, salva dal **pannello config** (profilo Marcato) oppure rigenera `config.js` dal repo con Python (vedi `tools/write_config_js.py`, argomento `overlay_root`).

### 3. Importa o seleziona la collezione in OBS

1. Apri OBS.
2. Menu **Scene Collection** (Collezione scene) → **Import**.
3. Scegli `obs\S_Marcato_42.json` dalla cartella del repo.
4. Se la collezione è già importata: **Scene Collection → S.Marcato 42**.

Scene previste (come PiGreco): Starting Soon, Live Race, Live Singolo, BRB, Ending — overlay da `overlays-marcato/`, canvas **1920×1080**.

### 4. Pannello config (profilo Marcato)

Avvia il server config (come per PiGreco):

- Doppio clic su `Start-ConfigPanel.bat` (lascia la finestra aperta).

In OBS, dock **Custom Browser Dock**:

| Campo | Valore |
|-------|--------|
| Nome | es. `S.Marcato Config` |
| URL | `http://127.0.0.1:8766/?profile=marcato` |

Salva dal pannello → rigenera `overlays-marcato/config.js` → **Refresh** sui Browser Source delle scene Marcato (o riavvia le scene).

Dettagli: [`docs/OBS_CONFIG_PANEL.md`](OBS_CONFIG_PANEL.md) (sezione **Profilo S.Marcato**).

### 5. Sponsor: disabilitati per design

`overlays-marcato/config.values.json` ha `sponsorsEnabled: false`. Gli HTML Marcato **non** montano `sponsors.js` — non compare alcuno slot sponsor (né placeholder PiGreco).

### 6. PiGreco affiancato

- Collezione team: **PiGreco Racing** (`obs/PiGreco_Racing.json`, `overlays/`).
- Collezione personale: **S.Marcato 42** (`obs/S_Marcato_42.json`, `overlays-marcato/`).

Passa da **Scene Collection** quando cambi stream (team vs personale). Il pannello config usa `?profile=marcato` solo quando lavori sul pack Marcato; per PiGreco usa `http://127.0.0.1:8766/` (default).

## Stinger transition (steel wipe)

Short wipe (~**0.8 s**) for OBS **Stinger** scene changes: dark panel, steel/white leading edge, center mark **42** (Syne, no PiGreco green flash or π logo).

### Assets

| Path | Use |
|------|-----|
| [`overlays-marcato/stinger/index.html`](../overlays-marcato/stinger/index.html) | Preview / record-from-browser helper |
| PiGreco reference timing | Same ~800 ms keyframes as [`overlays/stinger/`](../overlays/stinger/) — see [`docs/STINGER.md`](STINGER.md) |

Preview in a browser:

`overlays-marcato/stinger/index.html?preview=1`  
(optional `&loop=1` to repeat, **Replay** button in preview mode)

### OBS setup

1. Open OBS → **Settings** → **Scene Transitions** (or the Transitions dock).
2. Click **+** → **Stinger**.
3. Name it e.g. `S.Marcato 42 Stinger`.
4. **Video file** (recommended after you record/export one cycle from the HTML preview), **or** use a temporary **Browser Source** on a record scene pointing at  
   `…\obs-pigreco-racing\overlays-marcato\stinger\index.html`  
   (1920×1080, transparent background).
5. **Transition point**: start at **~50%** (~**400 ms** on an 800 ms clip) — cut while the frame is fully covered (`42` visible), before the reveal wipe.
6. **Audio**: unset unless you add a whoosh later.
7. Set as default or pick per scene switch; test Starting Soon ↔ Live (or your marcato scenes).

### Tips

- Canvas **1920×1080** (pack default).
- Nudge transition point a few percent if the cut feels early (lower %) or late (higher %).
- Do not leave the stinger as a permanent overlay on race scenes — use **Transitions → Stinger** only.

### Do not

- Do not use PiGreco green stinger media for the marcato collection.
- Do not loop the sting on-air; one shot per scene change.

## Riferimenti

- Design: [`docs/superpowers/specs/2026-08-01-s-marcato-42-design.md`](superpowers/specs/2026-08-01-s-marcato-42-design.md)
- Stinger generico: [`docs/STINGER.md`](STINGER.md)
