@echo off
REM Double-click this file to configure the PiGreco OBS pack.
cd /d "%~dp0"
echo.
echo PiGreco Racing - Setup OBS
echo ==========================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if %ERR% NEQ 0 (
  echo Setup terminato con errori. Codice: %ERR%
) else (
  echo Fatto. Puoi chiudere questa finestra.
)
pause
exit /b %ERR%
