#Requires -Version 5.1
# Bootstrap: scarica main da GitHub ed esegue Setup.ps1
# Uso: irm https://raw.githubusercontent.com/marcatos/obs-pigreco-racing/main/install.ps1 | iex
$ErrorActionPreference = 'Stop'
$zipUrl = 'https://github.com/marcatos/obs-pigreco-racing/archive/refs/heads/main.zip'
$zipFile = Join-Path $env:TEMP 'obs-pigreco-racing.zip'
$destRoot = Join-Path $env:USERPROFILE 'Documents'
$destDir = Join-Path $destRoot 'obs-pigreco-racing-main'
[Net.ServicePointManager]::SecurityProtocol = 'Tls12'
Write-Host ''
Write-Host 'PiGreco Racing OBS - download da GitHub...' -ForegroundColor Green
Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing
if (Test-Path $destDir) {
    Remove-Item $destDir -Recurse -Force
}
Expand-Archive -Path $zipFile -DestinationPath $destRoot -Force
$setup = Join-Path $destDir 'Setup.ps1'
if (-not (Test-Path $setup)) {
    Write-Host "Setup non trovato: $setup" -ForegroundColor Red
    exit 1
}
Write-Host 'Avvio Setup (scegli pack OBS, default = solo PiGreco)...' -ForegroundColor Cyan
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup
exit $LASTEXITCODE
