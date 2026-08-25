param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path $RepoRoot).Path
$runDir = Join-Path $repoRoot ".run"
$logDir = Join-Path $repoRoot "logs"
$pidPath = Join-Path $runDir "backend.pid"
$stdoutPath = Join-Path $logDir "backend.out.log"
$stderrPath = Join-Path $logDir "backend.err.log"
$backendDir = Join-Path $repoRoot "backend"
$cudaBinDir = Join-Path $repoRoot "tools\cuda\bin"

New-Item -ItemType Directory -Force -Path $runDir, $logDir | Out-Null
Set-Content -Path $pidPath -Value $PID -Encoding ascii
Set-Location $backendDir

if (
    (Test-Path (Join-Path $cudaBinDir "cublas64_12.dll")) -and
    (Test-Path (Join-Path $cudaBinDir "cudnn64_9.dll"))
) {
    $env:PATH = "$cudaBinDir;$env:PATH"
}

try {
    $command = 'uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 1>"{0}" 2>"{1}"' -f $stdoutPath, $stderrPath
    & cmd.exe /c $command
    exit $LASTEXITCODE
} finally {
    Remove-Item -Path $pidPath -Force -ErrorAction SilentlyContinue
}
