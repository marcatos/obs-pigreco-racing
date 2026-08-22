#Requires -Version 5.1
<#
.SYNOPSIS
  Setup guidato del pacchetto OBS PiGreco Racing.

.DESCRIPTION
  - Chiede nick / nome pilota
  - Se Python non e' installato, lo installa (richiede privilegi elevati)
  - Installa dipendenze Python (requirements-setup.txt)
  - Verifica / installa OBS Studio se assente (winget)
  - Personalizza config e copia la collezione scene in OBS

.PARAMETER Username
  Nick Twitch senza @

.PARAMETER PilotName
  Nome visualizzato negli overlay

.PARAMETER TeamName
  Default: PiGreco Racing

.PARAMETER EventTitle
  Default: Sim Racing Session

.PARAMETER Profiles
  Pack OBS da installare: pigreco, marcato (virgola). Default: pigreco

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
    [string]$Profiles = "",
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
            "-EventTitle", $EventTitle,
            "-Profiles", $Profiles
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

function Ensure-Pip {
    param([string]$PythonExe)
    Write-Log INFO "Verifica pip"
    & $PythonExe -m pip --version 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log INFO "Bootstrap pip ..."
        & $PythonExe -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) {
            throw "ensurepip fallito"
        }
    }
    Write-Log INFO "Aggiornamento pip ..."
    & $PythonExe -m pip install --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade fallito"
    }
}

function Ensure-PipRequirements {
    param([string]$PythonExe, [string]$RequirementsFile)
    if (-not (Test-Path $RequirementsFile)) {
        throw "File mancante: $RequirementsFile"
    }
    Write-Log INFO "Installazione dipendenze Python da $(Split-Path -Leaf $RequirementsFile) ..."
    $t0 = Get-Date
    & $PythonExe -m pip install --disable-pip-version-check -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) {
        throw "pip install -r $RequirementsFile fallito"
    }
    $ms = [int]((Get-Date) - $t0).TotalMilliseconds
    Write-Log INFO "pip requirements completato in ${ms}ms"
}

function Find-ObsExecutable {
    $paths = @(
        "$env:ProgramFiles\obs-studio\bin\64bit\obs64.exe",
        "${env:ProgramFiles(x86)}\obs-studio\bin\64bit\obs64.exe",
        "$env:LOCALAPPDATA\Programs\obs-studio\bin\64bit\obs64.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Install-ObsWithWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        return $false
    }
    Write-Log INFO "Installazione OBS Studio tramite winget (scope user) ..."
    $t0 = Get-Date
    & winget install -e --id OBSProject.OBSStudio --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
    $code = $LASTEXITCODE
    $ms = [int]((Get-Date) - $t0).TotalMilliseconds
    Write-Log INFO "winget OBS (user) exit=$code in ${ms}ms"
    if (Find-ObsExecutable) {
        return $true
    }
    if (Test-IsAdmin) {
        Write-Log INFO "Retry OBS winget (machine scope) ..."
        & winget install -e --id OBSProject.OBSStudio --accept-package-agreements --accept-source-agreements --disable-interactivity
        return [bool](Find-ObsExecutable)
    }
    return $false
}

function Ensure-ObsStudio {
    $obs = Find-ObsExecutable
    if ($obs) {
        Write-Log INFO "OBS Studio trovato: $obs"
        return $obs
    }
    Write-Log WARN "OBS Studio non trovato"
    if (Install-ObsWithWinget) {
        $obs = Find-ObsExecutable
        Write-Log INFO "OBS Studio installato: $obs"
        return $obs
    }
    Write-Log WARN "Installa OBS manualmente da https://obsproject.com e rilancia Setup se necessario"
    return $null
}

function Test-MoveTransitionPlugin {
    $dll = 'C:\Program Files\obs-studio\obs-plugins\64bit\move-transition.dll'
    if (Test-Path $dll) {
        Write-Log INFO "Plugin Move Transition presente"
        return $true
    }
    Write-Log WARN "Plugin Move Transition assente ($dll) - transizioni Move nel pack potrebbero non funzionare; vedi docs/TRANSITIONS.md"
    return $false
}

function Read-Required([string]$Prompt, [string]$Current) {
    if ($Current -and $Current.Trim()) { return $Current.Trim() }
    while ($true) {
        $v = Read-Host $Prompt
        if ($v -and $v.Trim()) { return $v.Trim() }
        Write-Host "Valore obbligatorio." -ForegroundColor Yellow
    }
}

function Read-ProfileChoice {
    Write-Host ""
    Write-Host "Pack OBS da installare:" -ForegroundColor Cyan
    Write-Host "  [1] Solo PiGreco Racing (consigliato per il team)" -ForegroundColor White
    Write-Host "  [2] PiGreco + S.Marcato 42" -ForegroundColor White
    Write-Host "  [3] Solo S.Marcato 42" -ForegroundColor White
    $choice = Read-Host "Scelta [Invio = 1]"
    if (-not $choice -or $choice -eq "1") { return "pigreco" }
    switch ($choice) {
        "2" { return "pigreco,marcato" }
        "3" { return "marcato" }
        default { return "pigreco" }
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

    if (-not $Profiles) {
        $Profiles = Read-ProfileChoice
    }
    Write-Log INFO "profiles=$Profiles"

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
    Ensure-Pip -PythonExe $python
    $requirements = Join-Path $ScriptDir "requirements-setup.txt"
    Ensure-PipRequirements -PythonExe $python -RequirementsFile $requirements
    $verifyDeps = Join-Path $ScriptDir "tools\verify_setup_dependencies.py"
    if (-not (Test-Path $verifyDeps)) {
        throw "File mancante: tools\verify_setup_dependencies.py"
    }
    Write-Log INFO "Verifica import dipendenze Python ..."
    & $python $verifyDeps
    if ($LASTEXITCODE -ne 0) {
        throw "Verifica dipendenze Python fallita"
    }

    Ensure-ObsStudio | Out-Null
    Test-MoveTransitionPlugin | Out-Null

    $setupPy = Join-Path $ScriptDir "tools\setup_streamer.py"
    if (-not (Test-Path $setupPy)) {
        throw "File mancante: tools\setup_streamer.py"
    }

    $args = @(
        $setupPy,
        "--username", $Username,
        "--pilot-name", $PilotName,
        "--team-name", $TeamName,
        "--event-title", $EventTitle,
        "--profiles", $Profiles
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

    $integrate = Join-Path $ScriptDir "tools\pigreco_install.py"
    if (-not (Test-Path $integrate)) {
        throw "File mancante: tools\pigreco_install.py"
    }
    Write-Log INFO "Integrazione OBS (dock PiGreco Config, autostart, telemetria)..."
    & $python $integrate install --pack-root $ScriptDir --profiles $Profiles
    if ($LASTEXITCODE -ne 0) {
        throw "pigreco_install.py exit code $LASTEXITCODE"
    }

    $totalMs = [int]((Get-Date) - $Script:StartedAt).TotalMilliseconds
    Write-Host ""
    Write-Host "SETUP COMPLETATO" -ForegroundColor Green
    Write-Host "1) Apri OBS Studio (o riavvialo se era gia' aperto)" -ForegroundColor White
    Write-Host '2) Menu Collezione di scene -> PiGreco Racing' -ForegroundColor White
    Write-Host "3) Visualizza -> Docks -> PiGreco Config (pannello impostazioni)" -ForegroundColor White
    Write-Host "4) Telemetria + Session Director partono in automatico (porte 8765/8766)" -ForegroundColor White
    Write-Host "5) Guida completa: Guida_PiGreco_OBS.pdf" -ForegroundColor White
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
