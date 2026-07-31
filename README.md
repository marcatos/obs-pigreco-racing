# OBS PiGreco Racing

Collezione scene OBS per streaming sim racing (triplo monitor + monitor singolo), con StreamCam e overlay a brand **PiGreco Racing**.

## Contenuto

| Percorso | Descrizione |
|----------|-------------|
| `obs/PiGreco_Racing.json` | Collezione scene OBS |
| `overlays/*.html` | Browser Source (Starting / Live / BRB / Ending) |
| `overlays/config.js` | Testi editabili (pilota, evento, handle) |
| `overlays/assets/` | Logo, theme, hero |
| `overlays/assets/official/` | Asset scaricati da [pigrecoracing.com](https://www.pigrecoracing.com/) |

### Scene

1. **Starting Soon** — overlay fullscreen + StreamCam
2. **Live Race** — Display Capture monitor centrale + chrome live + StreamCam
3. **Live Singolo** — Display Capture quarto monitor + stessi overlay
4. **BRB** — “Torno subito” + webcam
5. **Ending** — grazie + handle Twitch

Canvas / uscita: **1920×1080**.

## Installazione OBS

1. Chiudi OBS (consigliato).
2. Copia `obs/PiGreco_Racing.json` in:
   `%APPDATA%\obs-studio\basic\scenes\`
3. Apri OBS → **Scene Collection** → seleziona **PiGreco Racing**  
   (se non compare: *Import* / riapri OBS).
4. Nelle sorgenti **Monitor Centro** e **Monitor Singolo**: apri Proprietà e scegli il display corretto  
   - triplo acceso → Centro = monitor centrale della pista  
   - solo quarto monitor → usa scena **Live Singolo** e seleziona quel display
5. Verifica **StreamCam** (device Logitech StreamCam).
6. Gli overlay Browser Source puntano già a:
   `C:\Users\simot\Documents\Projects\obs-pigreco-racing\overlays\...`  
   Se sposti la cartella, aggiorna gli URL o riesegui `python tools/generate_pack.py`.

### Hotkey consigliate

In OBS → Impostazioni → Hotkey:

| Hotkey | Scena |
|--------|--------|
| F1 | Starting Soon |
| F2 | Live Race |
| F3 | Live Singolo |
| F4 | BRB |
| F5 | Ending |

## Personalizzare i testi

Modifica `overlays/config.js`, poi in OBS su ogni Browser Source: **Refresh cache of current page**.

Puoi anche passare override via query string, es.  
`live-chrome.html?eventTitle=iRacing%20Night&pilotName=...`

## Asset ufficiali

Prelevati da https://www.pigrecoracing.com/ :

- `images/restyle/logo-pigreco.png` (π verde)
- `images/logo.png` (wordmark PIGRECO RACING)
- `images/restyle/hero-racing.jpg`
- partner / social: SimGrid, Tektrama, GoSetups, Discord, Instagram
- palette da `css/pigreco-restyle.css` (`#00C400`, `#009FE5`, `#050505`)

Dettagli e licenza d’uso: vedi [ATTRIBUTION.md](ATTRIBUTION.md).

## Tool

```powershell
python tools/process_official_assets.py   # ri-processa loghi (fondo trasparente)
python tools/generate_pack.py             # rigenera PNG fallback + JSON OBS
```

## Note triplo monitor

I tre display sono separati (non Surround). In stream si acquisisce **solo il monitor centrale** per leggibilità. Il quarto monitor ha la scena dedicata **Live Singolo**.
