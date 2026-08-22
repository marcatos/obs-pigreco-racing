#Requires -Version 5.1
# Bootstrap: scarica main da GitHub, aggiorna/disinstalla se presente, esegue Setup.ps1
# Uso: irm https://raw.githubusercontent.com/marcatos/obs-pigreco-racing/main/install.ps1 | iex
$ErrorActionPreference = 'Stop'
$zipUrl = 'https://github.com/marcatos/obs-pigreco-racing/archive/refs/heads/main.zip'
$zipFile = Join-Path $env:TEMP 'obs-pigreco-racing.zip'
$destRoot = Join-Path $env:USERPROFILE 'Documents'
$destDir = Join-Path $destRoot 'obs-pigreco-racing-main'
$stateFile = Join-Path $env:LOCALAPPDATA 'PiGrecoOBS\install.json'
$stagingDir = Join-Path $env:TEMP 'obs-pigreco-racing-staging'
$stagingPack = Join-Path $stagingDir 'obs-pigreco-racing-main'

function Read-InstallAction {
    $existing = ''
    if (Test-Path $stateFile) {
        try {
            $json = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($json.pack_root) { $existing = [string]$json.pack_root }
        } catch { }
    }
    if (-not $existing -and (Test-Path $destDir)) {
        $existing = $destDir
    }
    if (-not $existing) {
        return 'install'
    }
    Write-Host ''
    Write-Host "Installazione esistente: $existing" -ForegroundColor Yellow
    Write-Host '  [1] Aggiorna (consigliato)' -ForegroundColor White
    Write-Host '  [2] Disinstalla' -ForegroundColor White
    Write-Host '  [3] Annulla' -ForegroundColor White
    $choice = Read-Host 'Scelta [Invio = 1]'
    if (-not $choice -or $choice -eq '1') { return 'update' }
    switch ($choice) {
        '2' { return 'uninstall' }
        '3' { return 'cancel' }
        default { return 'update' }
    }
}

function Download-AndExtract {
    [Net.ServicePointManager]::SecurityProtocol = 'Tls12'
    Write-Host 'Download pack da GitHub...' -ForegroundColor Green
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing
    if (Test-Path $stagingDir) {
        Remove-Item $stagingDir -Recurse -Force
    }
    Expand-Archive -Path $zipFile -DestinationPath $stagingDir -Force
    if (-not (Test-Path (Join-Path $stagingPack 'Setup.ps1'))) {
        throw "Pacchetto estratto non valido: $stagingPack"
    }
}

$action = Read-InstallAction
if ($action -eq 'cancel') {
    Write-Host 'Annullato.' -ForegroundColor Yellow
    exit 0
}

if ($action -eq 'uninstall') {
    $pack = $destDir
    if (Test-Path $stateFile) {
        try {
            $json = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($json.pack_root) { $pack = [string]$json.pack_root }
        } catch { }
    }
    $integrate = Join-Path $pack 'tools\pigreco_install.py'
    $py = $null
    foreach ($cmd in @('python', 'py')) {
        $c = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($c) { $py = $c.Source; break }
    }
    if ($py -and (Test-Path $integrate)) {
        & $py $integrate uninstall --pack-root $pack --remove-pack-dir
    }
    if (Test-Path $pack) {
        Remove-Item $pack -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $stateFile) {
        Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
    }
    Write-Host 'Disinstallazione completata.' -ForegroundColor Green
    exit 0
}

Download-AndExtract

if ($action -eq 'update' -and (Test-Path $destDir)) {
    Write-Host 'Aggiornamento file pack (config pilota conservata)...' -ForegroundColor Cyan
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) {
        throw 'Python richiesto per aggiornare il pack. Installa Python e rilancia.'
    }
    $syncScript = Join-Path $stagingPack 'tools\pigreco_install.py'
    & $py.Source $syncScript sync $stagingPack $destDir
    if ($LASTEXITCODE -ne 0) {
        throw "Sync pack fallito exit=$LASTEXITCODE"
    }
} else {
    if (Test-Path $destDir) {
        Remove-Item $destDir -Recurse -Force
    }
    Copy-Item -Path $stagingPack -Destination $destDir -Recurse -Force
}

$setup = Join-Path $destDir 'Setup.ps1'
if (-not (Test-Path $setup)) {
    Write-Host "Setup non trovato: $setup" -ForegroundColor Red
    exit 1
}
Write-Host 'Avvio Setup (nick, dipendenze, pack OBS, pannello PiGreco)...' -ForegroundColor Cyan
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup
exit $LASTEXITCODE
