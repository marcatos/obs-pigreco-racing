# OBS Config Panel (Custom Browser Dock)

> **EN:** An **in-OBS Custom Browser Dock** at `http://127.0.0.1:8766/` so you change nick, session badge, countdown, BRB, ending, sponsors, and telecronaca toggles **without hand-editing overlay files**. Saves to `config.values.json` for the active profile and regenerates `config.js`. Switch PiGreco ↔ S.Marcato with `?profile=marcato` or the profile dropdown. Localhost only.

Public overview: [`../README.md#config-dock--change-the-stream-without-editing-files`](../README.md#config-dock--change-the-stream-without-editing-files).

## Cosa fa

Un **pannellino dentro OBS** (dock) per cambiare nick, sessione, countdown, BRB, ending, sponsor **senza editare file a mano**.

Salva su **`config.values.json`** nel profilo overlay attivo e rigenera il rispettivo `config.js`:

| Profilo | Cartella | File valori |
|---------|----------|-------------|
| PiGreco (default) | `overlays/` | `overlays/config.values.json` |
| S.Marcato | `overlays-marcato/` | `overlays-marcato/config.values.json` |

## Setup (una volta)

1. **Autostart (due livelli)**  
   - **OBS Scripts (Lua):** nelle collezioni generate è cablato  
     `obs/scripts/pigreco_config_autostart.lua` — parte **una sola volta** all’apertura di OBS  
     (ShellExecute nascosto, niente timer / niente console nera).  
     Avvia **config :8766** e **Session Director + telemetria :8765**.  
     Se in Scripts vedi ancora `pigreco_config_autostart.py`, **rimuovilo** (è disattivato).  
   - **Windows Startup (opzionale, solo config server):**  
     `powershell -File tools/install_config_autostart.ps1`  
     Per rimuoverlo: `powershell -File tools/install_config_autostart.ps1 -Remove`

2. Dock browser (se non c’è già):

   - **Visualizza → Docks → Custom Browser Docks…**
   - **Dock Name:** `PiGreco Config`
   - **URL:** `http://127.0.0.1:8766/`
   - Apply / Close

3. (Opzionale) Avvio manuale / emergenza:

   ```bat
   Start-ConfigPanel.bat
   ```

   Usa `tools/ensure_config_server.py` (idempotente, lascia il server in background).

4. Refresh overlay dopo Salva: script OBS Python legacy  
   `obs/scripts/pigreco_refresh_browsers.py` (se Python OBS funziona),  
   oppure tasto destro sulla Browser Source → Refresh cache.

## Uso quotidiano

1. Apri OBS (lo script Lua avvia il config server)  
2. Apri il dock **PiGreco Config** (Visualizza → Docks)  
3. Modifica i campi → **Salva e applica**  
4. Refresh browser (manuale o script)

Se il dock è bianco: il server non è su. In **Strumenti → Scripts** seleziona  
`pigreco_config_autostart.lua` → **Avvia / verifica config server ora**,  
oppure `Start-ConfigPanel.bat`.

## Profilo S.Marcato

Per editare `overlays-marcato/config.values.json` invece del pack PiGreco:

- **URL dock OBS (S.Marcato):** `http://127.0.0.1:8766/?profile=marcato`
- In alternativa: apri `http://127.0.0.1:8766/` e usa **Profilo overlay → S.Marcato** (ricarica con `?profile=marcato`).
- Salva e applica come sopra; rigenera `overlays-marcato/config.js`.

Il dock può restare su un solo URL: cambia profilo dal menu a tendina (ricarica la pagina con `?profile=`).

## Telecronaca (P3-02)

Nel fieldset **Telemetria / broadcast**:

- **Overlay broadcast attivo** → `telemetryEnabled` (default off: nessuna connessione WS)
- URL WebSocket (default `ws://127.0.0.1:8765`)
- Toggle classifica / relative / focus / session strip

Avvio producer (processo esterno, non da OBS Scripts):

```bat
Start-Telemetry.bat mock
Start-Telemetry.bat iracing
```

Poi in OBS: occhio su **Overlay Broadcast Chrome**. Dettagli: [`docs/TELEMETRY_BROADCAST.md`](TELEMETRY_BROADCAST.md).

## Note

- Il server ascolta solo su `127.0.0.1` (locale).
- Fonte di verità: **`config.values.json` nel profilo scelto** (`overlays/` o `overlays-marcato/`).
- `config.js` è **generato** — non editarlo a lungo termine.
- `Setup.ps1` / `setup_streamer.py` aggiornano lo stesso JSON del profilo PiGreco.
- **Dopo un aggiornamento del pack** (nuovo supporto profili o dock che non carica / non salva): chiudi il server config, riavvia `Start-ConfigPanel.bat`, poi ricarica il dock OBS (URL con `?profile=` se usi S.Marcato).
