@echo off
cd /d "%~dp0"
echo.
echo PiGreco / S.Marcato - Session Director (OBS scenes)
echo ==================================================
echo.
echo Flags + Live/Lobby automation via telemetry + iRacing process watch.
echo Requires: OBS WebSocket :4455 (see docs\OBS_VIRTUALDECK.md)
echo Config:   adapters\obs_flag_director\config.local.json
echo Docs:     docs\SESSION_DIRECTOR.md  docs\FLAG_DIRECTOR.md
echo.
echo Default is dry-run until you set dryRun=false and OBS password.
echo.

if not exist "adapters\obs_flag_director\config.local.json" (
  copy /Y "adapters\obs_flag_director\config.example.json" "adapters\obs_flag_director\config.local.json" >nul
  echo Created adapters\obs_flag_director\config.local.json from example.
  echo Edit obsPassword and set dryRun=false when ready.
  echo.
)

python adapters\obs_flag_director\director.py %*
echo.
pause
