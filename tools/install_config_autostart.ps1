# Install / remove a Windows Startup shortcut that keeps the config panel
# server warm (127.0.0.1:8766) even before OBS opens.
#
# Uses the silent VBS launcher (no console window).
#
# Usage:
#   powershell -File tools/install_config_autostart.ps1
#   powershell -File tools/install_config_autostart.ps1 -Remove

[CmdletBinding()]
param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Vbs = Join-Path $Root "tools\ensure_config_server_silent.vbs"
$Ensure = Join-Path $Root "tools\ensure_config_server.py"
$Startup = [Environment]::GetFolderPath("Startup")
$LnkPath = Join-Path $Startup "PiGreco Config Server.lnk"
$LogDir = Join-Path $Root "logs"
$LogFile = Join-Path $LogDir "install_config_autostart.log"

function Write-Log([string]$Level, [string]$Message) {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1} {2}" -f (Get-Date), $Level, $Message
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

$t0 = Get-Date
Write-Log INFO "start install_config_autostart Remove=$Remove root=$Root"

if ($Remove) {
    if (Test-Path $LnkPath) {
        Remove-Item -Force $LnkPath
        Write-Log INFO "removed $LnkPath"
    } else {
        Write-Log INFO "shortcut already absent"
    }
    $elapsed = [int]((Get-Date) - $t0).TotalMilliseconds
    Write-Log INFO "done in ${elapsed}ms"
    exit 0
}

if (-not (Test-Path $Vbs)) {
    Write-Log ERROR "missing $Vbs"
    exit 2
}
if (-not (Test-Path $Ensure)) {
    Write-Log ERROR "missing $Ensure"
    exit 2
}

$wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
if (-not (Test-Path $wscript)) {
    $wscript = "wscript.exe"
}

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($LnkPath)
$lnk.TargetPath = $wscript
$lnk.Arguments = "//nologo `"$Vbs`""
$lnk.WorkingDirectory = $Root
$lnk.WindowStyle = 7
$lnk.Description = "PiGreco / S.Marcato config panel server (silent)"
$lnk.Save()

Write-Log INFO "shortcut -> $LnkPath"
Write-Log INFO "target $wscript //nologo $Vbs"

& $wscript //nologo $Vbs
$rc = $LASTEXITCODE
$elapsed = [int]((Get-Date) - $t0).TotalMilliseconds
if ($rc -ne 0) {
    Write-Log ERROR "silent ensure exit=$rc (shortcut still installed) in ${elapsed}ms"
    exit $rc
}
Write-Log INFO "done ok in ${elapsed}ms"
exit 0
