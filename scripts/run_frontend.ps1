param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path $RepoRoot).Path
$runDir = Join-Path $repoRoot ".run"
$logDir = Join-Path $repoRoot "logs"
$pidPath = Join-Path $runDir "frontend.pid"
$stdoutPath = Join-Path $logDir "frontend.out.log"
$stderrPath = Join-Path $logDir "frontend.err.log"
$frontendDir = Join-Path $repoRoot "frontend"
$lanDevServer = Join-Path $frontendDir "start-lan-dev-server.mjs"

New-Item -ItemType Directory -Force -Path $runDir, $logDir | Out-Null
Set-Content -Path $pidPath -Value $PID -Encoding ascii
Set-Location $frontendDir

if (-not (Test-Path -LiteralPath $lanDevServer)) {
    throw "LAN development server entry was not found: $lanDevServer."
}

try {
    # Expose only the Vite frontend on all interfaces. API traffic is proxied to
    # the backend, which remains bound to 127.0.0.1:8001.
    # Keep a hidden Node child process alive in non-interactive startup sessions.
    $nodeStartParams = @{
        FilePath               = (Get-Command node.exe -ErrorAction Stop).Definition
        ArgumentList           = @("`"$lanDevServer`"")
        WorkingDirectory       = $frontendDir
        WindowStyle            = "Hidden"
        RedirectStandardOutput = $stdoutPath
        RedirectStandardError  = $stderrPath
        PassThru               = $true
    }
    $nodeProcess = Start-Process @nodeStartParams

    $nodeProcess.WaitForExit()
    exit $nodeProcess.ExitCode
} finally {
    Remove-Item -Path $pidPath -Force -ErrorAction SilentlyContinue
}
