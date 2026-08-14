@echo off
setlocal
cd /d "%~dp0"
echo === PiGreco / S.Marcato — Sync iRacing track maps ===
echo Default: paths-dump (no login; official outlines).
echo API mode needs OAuth client_id/secret: Start-SyncTrackMaps.bat --source api
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
