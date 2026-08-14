@echo off
cd /d "%~dp0"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=mock"

echo.
echo PiGreco / S.Marcato - Telemetry (telecronaca)
echo =============================================
echo.
echo Mode: %MODE%  (mock / iracing)
echo Porta: ws://127.0.0.1:8765
echo.
echo 1) Lascia questa finestra aperta
echo 2) Pannello config - Overlay broadcast attivo
echo 3) OBS - occhio su Overlay Broadcast Chrome
echo.
echo Guida: docs\TELEMETRY_BROADCAST.md
echo.

if /I "%MODE%"=="iracing" goto run_iracing
if /I "%MODE%"=="mock" goto run_mock
echo Uso: Start-Telemetry.bat [mock^|iracing]
pause
exit /b 1

:run_iracing
python tools\start_telemetry.py iracing
goto done

:run_mock
python tools\start_telemetry.py mock
goto done

:done
echo.
pause