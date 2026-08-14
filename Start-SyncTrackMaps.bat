@echo off
setlocal
cd /d "%~dp0"
echo === PiGreco / S.Marcato — Sync iRacing track map SVGs ===
echo Credentials: IRACING_EMAIL + IRACING_PASSWORD
echo   or adapters\telemetry\iracing_api.local.json
echo.
python adapters\telemetry\sync_iracing_track_maps.py %*
set ERR=%ERRORLEVEL%
echo.
if %ERR% neq 0 (
  echo Sync finished with errors. See logs above.
) else (
  echo Sync finished. Cache: overlays\assets\tracks\iracing\
)
pause
exit /b %ERR%
