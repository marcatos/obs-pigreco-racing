@echo off
cd /d "%~dp0"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=mock"

echo.
echo PiGreco / S.Marcato - Telecronaca toolkit
echo =========================================
echo.
echo Starts:
echo   1) Config panel server :8766  (if not already up)
echo   2) Telemetry WS :8765         (mode=%MODE%)
echo   3) Flag director              (dry-run until you edit config.local.json)
echo.
echo OBS checklist:
echo   - Import/reimport S.Marcato Replay or Rec 2K after generate_pack
echo   - Eye ON: Overlay Broadcast Chrome (+ Track Map if wanted)
echo   - Dock: http://127.0.0.1:8766/?profile=marcato
echo   - Enable telemetryEnabled (+ trackMapEnabled)
echo   - Sync track SVGs once: Start-SyncTrackMaps.bat
echo.
echo Docs: docs\TELEMETRY_BROADCAST.md  docs\FLAG_DIRECTOR.md  docs\TRACK_MAP.md
echo.

start "PiGreco Config :8766" cmd /c "Start-ConfigPanel.bat"
timeout /t 2 /nobreak >nul
start "PiGreco Telemetry :8765" cmd /c "Start-Telemetry.bat %MODE%"
timeout /t 1 /nobreak >nul
start "PiGreco Flag Director" cmd /c "Start-FlagDirector.bat"
echo.
echo Launched 3 windows. Leave them open while streaming.
pause
