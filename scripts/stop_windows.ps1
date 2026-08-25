param(
    [switch]$ShowWindows
)

$ErrorActionPreference = "Stop"

$startScript = Join-Path $PSScriptRoot "start_windows.ps1"

if ($ShowWindows) {
    & $startScript -StopOnly -ShowWindows
} else {
    & $startScript -StopOnly
}
