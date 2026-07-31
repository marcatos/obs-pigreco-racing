# OBS Config Panel (Custom Browser Dock)

## Cosa fa

Un **pannellino dentro OBS** (dock) per cambiare nick, sessione, countdown, BRB, ending, sponsor **senza editare file a mano**.

Salva su `overlays/config.values.json` e rigenera `overlays/config.js`.

## Setup (una volta)

1. Avvia il server (lascia la finestra aperta):

   ```bat
   Start-ConfigPanel.bat
   ```

   Oppure: `python tools\config_server.py`

2. In OBS: **Visualizza (View) → Docks → Custom Browser Docks…**
   - **Dock Name:** `PiGreco Config`
   - **URL:** `http://127.0.0.1:8766/`
   - Apply / Close

3. Sposta il dock dove ti è comodo (accanto a Controlli / Audio).

4. (Consigliato) Script refresh:
   - OBS → **Strumenti / Tools → Scripts**
   - `+` → scegli `obs/scripts/pigreco_refresh_browsers.py`
   - Dopo ogni **Salva e applica** nel pannello, clicca **Refresh overlay Browser Sources**

Se non usi lo script: su ogni Browser Source overlay → tasto destro → **Refresh cache of current page**.

## Uso quotidiano

1. `Start-ConfigPanel.bat` acceso  
2. Modifica i campi nel dock **PiGreco Config**  
3. **Salva e applica**  
4. Refresh browser (script o manuale)  

## Note

- Il server ascolta solo su `127.0.0.1` (locale).
- Fonte di verità: `overlays/config.values.json`.
- `config.js` è **generato** — non editarlo a lungo termine.
- `Setup.ps1` / `setup_streamer.py` aggiornano lo stesso JSON.
