# OBS PiGreco Racing

Collezione scene OBS per streaming sim racing (triplo monitor + monitor singolo), con StreamCam e overlay a brand **PiGreco Racing**.

**Direzione prodotto / multi-agente:** parti da [`STRATEGY.md`](STRATEGY.md) e [`AGENTS.md`](AGENTS.md). Backlog: [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Showcase

Anteprime 1920×1080 in [`showcase/`](showcase/) (apri [`showcase/index.html`](showcase/index.html)):

| File | Scena |
|------|--------|
| `01-starting-soon.png` | Starting Soon |
| `02-live-chrome.png` | Live Race / Live Singolo (chrome + mock gameplay) |
| `03-brb.png` | BRB |
| `04-ending.png` | Ending |

Rigenera gli screenshot:

```powershell
python tools/generate_showcase.py
```

## Condivisione con il team

1. Condividi **tutta** la cartella del progetto (zip o copia).
2. Il compagno apre **`LEGGIMI.txt`** oppure fa doppio clic su **`Setup.bat`**.
3. Guida con immagini: **[`Guida_PiGreco_OBS.pdf`](Guida_PiGreco_OBS.pdf)**.

`Setup.bat` / `Setup.ps1`:
- chiede nick e nome
- se manca Python, lo installa con **privilegi amministratore** (UAC)
- personalizza gli overlay e installa la collezione in OBS

Alternativa da terminale (se Python c’è già):

```powershell
.\Setup.ps1 -Username SUO_NICK -PilotName "Nome Cognome"
# oppure
python tools/setup_streamer.py --username SUO_NICK --pilot-name "Nome Cognome" --install-obs
```

Rigenera PDF/screenshot:

```powershell
python tools/generate_showcase.py
python tools/generate_pdf_guide.py
```

## Parametri editabili

In [`overlays/config.js`](overlays/config.js):

| Chiave | Uso |
|--------|-----|
| `username` | Nick base (deriva anche l’handle se manca) |
| `pilotName` | Nome in lower-third / ending |
| `twitchHandle` | Handle con o senza `@` (normalizzato) |
| `teamName` | Brand watermark / label |
| `eventTitle` | Sottotitolo sessione |
| `tagline` | Motto |
| `startingMessage` / `brbMessage` / `endingMessage` / `endingSub` | Testi scene |
| `sponsors` | Lista loghi partner (rotazione in Live) |
| `sponsorDisplayMs` / `sponsorGapMs` | Quanto resta a schermo / pausa tra uno e l’altro |
| `sponsorsEnabled` | `false` per disattivare il rotator |

Gli sponsor in **Live Race / Live Singolo** compaiono in alto a sinistra, un logo alla volta, poi spariscono per non appesantire la gara. In Starting Soon restano in fila in basso.

Per aggiungere un partner: metti il PNG in `overlays/assets/official/` e aggiungi una riga in `sponsors`.

Override al volo via query string sul Browser Source, es.:

`live-chrome.html?username=altro_nick&eventTitle=PiGreco%20Night`

Dopo ogni modifica a `config.js`: in OBS → Browser Source → **Refresh cache of current page**.

## Contenuto

| Percorso | Descrizione |
|----------|-------------|
| `Setup.bat` / `Setup.ps1` | **Setup guidato** (installa Python se manca + configura OBS) |
| `Guida_PiGreco_OBS.pdf` | Istruzioni semplificate con grafiche PiGreco |
| `LEGGIMI.txt` | Promemoria rapido in chiaro |
| `obs/PiGreco_Racing.json` | Collezione scene OBS |
| `overlays/*.html` | Browser Source |
| `overlays/config.js` | Parametri streamer |
| `overlays/assets/` | Logo, theme, hero |
| `showcase/` | Screenshot per preview/share |
| `overlays/assets/official/` | Asset da [pigrecoracing.com](https://www.pigrecoracing.com/) |

### Scene

1. **Starting Soon** — overlay fullscreen + StreamCam  
2. **Live Race** — monitor centrale + chrome live + StreamCam  
3. **Live Singolo** — quarto monitor + stessi overlay  
4. **BRB** — “Torno subito” + webcam  
5. **Ending** — grazie + handle  

Canvas / uscita: **1920×1080** (OBS 32.x con `pos_rel` / `scale_rel`).

> Chiudi OBS prima di riscrivere `PiGreco_Racing.json`, altrimenti alla chiusura può sovrascrivere il file.

## Installazione OBS (manuale)

1. Chiudi OBS.
2. Copia `obs/PiGreco_Racing.json` in `%APPDATA%\obs-studio\basic\scenes\`  
   (oppure usa `--install-obs` con `setup_streamer.py`).
3. Apri OBS → **Scene Collection** → **PiGreco Racing**.
4. Imposta **Monitor Centro** / **Monitor Singolo** sul display corretto.
5. Verifica **StreamCam**.

### Hotkey consigliate

| Hotkey | Scena |
|--------|--------|
| F1 | Starting Soon |
| F2 | Live Race |
| F3 | Live Singolo |
| F4 | BRB |
| F5 | Ending |

### Stinger

Transizione scene brand (~0.8 s): WebM in [`overlays/stinger/pigreco-stinger.webm`](overlays/stinger/pigreco-stinger.webm).

In OBS → **Transitions** → **+** → **Stinger** → seleziona quel file → **Transition Point ~55%**. Guida completa: [`docs/STINGER.md`](docs/STINGER.md).

Anteprima HTML: `overlays/stinger/index.html?preview=1`.

## Engagement

Temi chat/alert PiGreco (StreamElements / preview OBS): [`adapters/streamelements/`](adapters/streamelements/).

## Asset ufficiali

Vedi [ATTRIBUTION.md](ATTRIBUTION.md). Palette: `#00C400`, `#009FE5`, `#050505`.

## Tool

```powershell
python tools/setup_streamer.py --username NICK --install-obs
python tools/generate_showcase.py
python tools/process_official_assets.py
python tools/generate_pack.py
python tools/generate_stinger.py
```

## Note triplo monitor

Tre display separati (non Surround). In stream si acquisisce **solo il monitor centrale**. Il quarto monitor usa **Live Singolo**.
