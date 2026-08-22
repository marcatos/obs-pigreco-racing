#Requires -Version 5.1
<#
.SYNOPSIS
  Setup guidato del pacchetto OBS PiGreco Racing.

.DESCRIPTION
  - Chiede nick / nome pilota
  - Se Python non e' installato, lo installa (richiede privilegi elevati)
  - Installa dipendenze minime (Pillow)
  - Personalizza config e copia la collezione scene in OBS

.PARAMETER Username
  Nick Twitch senza @

.PARAMETER PilotName
  Nome visualizzato negli overlay

.PARAMETER TeamName
  Default: PiGreco Racing

.PARAMETER EventTitle
  Default: Sim Racing Session

.PARAMETER SkipObsInstall
  Non copia il JSON in AppData OBS

.EXAMPLE
  .\Setup.ps1
  .\Setup.ps1 -Username marco92 -PilotName "Marco Rossi"
#>
[CmdletBinding()]
param(
    [string]$Username = "",
    [string]$PilotName = "",
    [string]$TeamName = "PiGreco Racing",
    [string]$EventTitle = "Sim Racing Session",
    [switch]$SkipObsInstall,
    [switch]$ElevatedPythonInstall
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$LogDir = Join-Path $ScriptDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("setup-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))
$Script:StartedAt = Get-Date

function Write-Log {
    param(
        [ValidateSet("DEBUG", "INFO", "WARN", "ERROR")]
        [string]$Level = "INFO",
        [Parameter(Mandatory)][string]$Message
    )
    $line = "{0:yyyy-MM-dd HH:mm:ss} [{1}] {2}" -f (Get-Date), $Level, $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    switch ($Level) {
        "ERROR" { Write-Host $line -ForegroundColor Red }
        "WARN"  { Write-Host $line -ForegroundColor Yellow }
        "DEBUG" { Write-Host $line -ForegroundColor DarkGray }
        default { Write-Host $line -ForegroundColor Cyan }
    }
}

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Request-Elevation {
    param([string[]]$ExtraArgs)
    Write-Log INFO "Riavvio PowerShell con privilegi elevati..."
    # Single argument string: reliable with UAC + paths with spaces
    $extra = ($ExtraArgs | ForEach-Object {
        if ($_ -match '\s') { '"{0}"' -f ($_ -replace '"', '\"') } else { $_ }
    }) -join ' '
    $argString = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" $extra"
    $p = Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argString -Wait -PassThru
    exit $p.ExitCode
}

function Find-Python {
    $candidates = @()

    foreach ($cmd in @("py", "python", "python3")) {
        $c = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($c) { $candidates += $c.Source }
    }

    $paths = @(
        "$env:LocalAppData\Programs\Python\Python312\python.exe",
        "$env:LocalAppData\Programs\Python\Python313\python.exe",
        "$env:LocalAppData\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "${env:ProgramFiles(x86)}\Python312\python.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { $candidates += $p }
    }

    foreach ($exe in ($candidates | Select-Object -Unique)) {
        try {
            $ver = & $exe -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver) {
                return $exe
            }
        } catch {
            continue
        }
    }
    # py -3 launcher
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $out = & py -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out -and (Test-Path $out.Trim())) {
                return $out.Trim()
            }
        } catch { }
    }
    return $null
}

function Refresh-PathFromMachine {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Install-PythonElevated {
    Write-Log INFO "Python non trovato: avvio installazione (servono privilegi amministratore)"

    if (-not (Test-IsAdmin)) {
        $passArgs = @(
            "-ElevatedPythonInstall",
            "-Username", $Username,
            "-PilotName", $PilotName,
            "-TeamName", $TeamName,
            "-EventTitle", $EventTitle
        )
        if ($SkipObsInstall) { $passArgs += "-SkipObsInstall" }
        Request-Elevation -ExtraArgs $passArgs
        return
    }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Log ERROR 'winget non disponibile. Installa Python a mano da https://www.python.org/downloads/ (spunta Add python.exe to PATH) e rilancia Setup.ps1'
        throw "winget missing"
    }

    Write-Log INFO "Installazione Python 3.12 tramite winget (puo' richiedere alcuni minuti)..."
    $t0 = Get-Date
    & winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --disable-interactivity
    $code = $LASTEXITCODE
    $ms = [int]((Get-Date) - $t0).TotalMilliseconds
    Write-Log INFO "winget terminato exit=$code in ${ms}ms"

    # 0 = ok, -1978335189 / other codes sometimes mean already installed
    Refresh-PathFromMachine
    Start-Sleep -Seconds 2

    $py = Find-Python
    if (-not $py) {
        Write-Log ERROR "Python ancora non trovato dopo l'installazione. Chiudi e riapri il terminale, poi rilancia Setup.ps1"
        throw "Python not on PATH after install"
    }
    Write-Log INFO "Python installato: $py"
}

function Ensure-Python {
    $py = Find-Python
    if ($py) {
        Write-Log INFO "Python trovato: $py"
        return $py
    }
    Install-PythonElevated
    Refresh-PathFromMachine
    $py = Find-Python
    if (-not $py) {
        throw "Impossibile trovare Python dopo l'installazione"
    }
    return $py
}

function Ensure-PipPackage {
    param([string]$PythonExe, [string]$Package)
    Write-Log INFO "Verifica pacchetto Python: $Package"
    & $PythonExe -m pip show $Package 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log INFO "Installazione $Package ..."
        & $PythonExe -m pip install --disable-pip-version-check $Package
        if ($LASTEXITCODE -ne 0) {
            throw "pip install $Package fallito"
        }
    } else {
        Write-Log INFO "$Package gia' presente"
    }
}

function Read-Required([string]$Prompt, [string]$Current) {
    if ($Current -and $Current.Trim()) { return $Current.Trim() }
    while ($true) {
        $v = Read-Host $Prompt
        if ($v -and $v.Trim()) { return $v.Trim() }
        Write-Host "Valore obbligatorio." -ForegroundColor Yellow
    }
}

# --- main ---
try {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host '  PiGreco Racing - Setup OBS Pack' -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Log INFO "start Setup.ps1 cwd=$ScriptDir log=$LogFile elevated=$(Test-IsAdmin) ElevatedPythonInstall=$ElevatedPythonInstall"

    if ($ElevatedPythonInstall -and -not (Test-IsAdmin)) {
        Write-Log ERROR "Flag ElevatedPythonInstall richiede admin"
        exit 1
    }

    $Username = Read-Required 'Il tuo nick Twitch (senza @)' $Username
    $Username = $Username.TrimStart('@')
    if (-not $PilotName) {
        $PilotName = Read-Host 'Nome visualizzato negli overlay (Invio = stesso del nick)'
        if (-not $PilotName) { $PilotName = $Username }
    }

    Write-Log INFO "streamer username=$Username pilot=$PilotName"

    if ($ElevatedPythonInstall) {
        # Siamo nell'istanza elevata dedicata all'install Python
        if (-not (Find-Python)) {
            Install-PythonElevated
        } else {
            Write-Log INFO "Python gia' presente in sessione elevata"
        }
    }

    $python = Ensure-Python
    Ensure-PipPackage -PythonExe $python -Package "Pillow"

    $setupPy = Join-Path $ScriptDir "tools\setup_streamer.py"
    if (-not (Test-Path $setupPy)) {
        throw "File mancante: tools\setup_streamer.py"
    }

    $args = @(
        $setupPy,
        "--username", $Username,
        "--pilot-name", $PilotName,
        "--team-name", $TeamName,
        "--event-title", $EventTitle
    )
    if (-not $SkipObsInstall) {
        $args += "--install-obs"
    }

    Write-Log INFO "Esecuzione setup_streamer.py ..."
    $t1 = Get-Date
    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw "setup_streamer.py exit code $LASTEXITCODE"
    }
    $ms = [int]((Get-Date) - $t1).TotalMilliseconds
    Write-Log INFO "setup_streamer completato in ${ms}ms"

    $autostart = Join-Path $ScriptDir "tools\install_config_autostart.ps1"
    if (Test-Path $autostart) {
        Write-Log INFO "Installazione autostart config server (Startup Windows)..."
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $autostart
        if ($LASTEXITCODE -ne 0) {
            Write-Log WARN "install_config_autostart exit=$LASTEXITCODE (puoi rilanciare tools/install_config_autostart.ps1)"
        }
    }

    $totalMs = [int]((Get-Date) - $Script:StartedAt).TotalMilliseconds
    Write-Host ""
    Write-Host "SETUP COMPLETATO" -ForegroundColor Green
    Write-Host "1) Apri OBS Studio" -ForegroundColor White
    Write-Host '2) Menu Collezione di scene -> PiGreco Racing' -ForegroundColor White
    Write-Host "3) Imposta Monitor Centro / Monitor Singolo e la webcam" -ForegroundColor White
    Write-Host "4) Guida completa: Guida_PiGreco_OBS.pdf" -ForegroundColor White
    Write-Host ""
    Write-Log INFO "done success total=${totalMs}ms"
    exit 0
}
catch {
    Write-Log ERROR $_.Exception.Message
    Write-Log ERROR "Dettagli nel log: $LogFile"
    Write-Host ""
    Write-Host "Setup non riuscito. Invia il file di log al referente tech:" -ForegroundColor Red
    Write-Host $LogFile -ForegroundColor Yellow
    exit 1
}
finally {
    if (-not $ElevatedPythonInstall) {
        Write-Host "Log: $LogFile" -ForegroundColor DarkGray
    }
}
