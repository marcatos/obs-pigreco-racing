@echo off
cd /d "%~dp0"
echo.
echo PiGreco / S.Marcato - Flag Director (OBS scenes)
echo ================================================
echo.
echo Requires: telemetry on ws://127.0.0.1:8765
echo Config:   adapters\obs_flag_director\config.local.json
echo Docs:     docs\FLAG_DIRECTOR.md
echo.
echo Default is dry-run until you set dryRun=false and OBS password.
echo.

python adapters\obs_flag_director\director.py %*
echo.
pause
