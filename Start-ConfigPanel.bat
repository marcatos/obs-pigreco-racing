@echo off
cd /d "%~dp0"
echo.
echo PiGreco Racing - Config Panel server
echo ====================================
echo.
echo Poi in OBS:
echo   Visualizza / View  -^>  Docks  -^>  Custom Browser Docks
echo   Nome: PiGreco Config
echo   URL:  http://127.0.0.1:8766/
echo.
echo Lascia questa finestra APERTA mentre usi OBS.
echo.
python tools\config_server.py
pause
