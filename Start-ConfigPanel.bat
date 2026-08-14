@echo off
cd /d "%~dp0"
echo.
echo PiGreco / S.Marcato — Config Panel
echo ==================================
echo.
echo Avvio (o verifica) del server su http://127.0.0.1:8766/
echo Il server resta in background: puoi chiudere questa finestra.
echo.
echo In OBS il dock "PiGreco Config" usera' quell'URL.
echo (Lo script Lua obs\scripts\pigreco_config_autostart.lua
echo  lo avvia anche da solo all'apertura di OBS.)
echo.
python tools\ensure_config_server.py
if errorlevel 1 (
  echo.
  echo ERRORE: server non partito. Controlla logs\config_server.log
  pause
  exit /b 1
)
echo.
echo OK — apri OBS → Visualizza → Docks → PiGreco Config
echo URL Marcato: http://127.0.0.1:8766/?profile=marcato
echo.
timeout /t 4 >nul
