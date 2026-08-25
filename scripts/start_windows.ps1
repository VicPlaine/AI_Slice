param(
    [switch]$ShowWindows,
    [switch]$StopOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$backendEnv = Join-Path $backendDir ".env"
$nodeModules = Join-Path $frontendDir "node_modules"
$runDir = Join-Path $repoRoot ".run"
$logDir = Join-Path $repoRoot "logs"
$windowStyle = if ($ShowWindows) { "Normal" } else { "Hidden" }

function Find-FfmpegBinDir {
    param([string]$Root)

    $candidates = [System.Collections.Generic.List[string]]@(
        (Join-Path $Root "tools\ffmpeg\bin"),
        (Join-Path $Root "ffmpeg\bin"),
        (Join-Path $Root "backend\tools\ffmpeg\bin")
    )

    $envPath = Join-Path $Root "backend\.env"
    if (Test-Path $envPath) {
        $configuredLine = Get-Content -LiteralPath $envPath |
            Where-Object { $_ -match '^\s*FFMPEG_BIN_DIR\s*=' } |
            Select-Object -First 1
        if ($configuredLine) {
            $configuredDir = ($configuredLine -split '=', 2)[1].Trim().Trim('"').Replace('/', '\')
            if ($configuredDir) {
                $candidates.Insert(0, $configuredDir)
            }
        }
    }

    foreach ($candidate in $candidates) {
        if (
            (Test-Path (Join-Path $candidate "ffmpeg.exe")) -and
            (Test-Path (Join-Path $candidate "ffprobe.exe"))
        ) {
            return $candidate
        }
    }

    return $null
}

function Write-Step {
    param([string]$Message)
    Write-Host "[ai-slice] $Message"
}

function Assert-Path {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path $Path)) {
        throw $Message
    }
}

function Invoke-TaskKill {
    param(
        [int]$ProcessId,
        [string]$Label
    )

    if ($ProcessId -le 0) {
        return
    }

    Write-Step "Closing $Label (PID $ProcessId)..."
    & taskkill.exe /PID $ProcessId /T /F | Out-Null
}

function Get-PidFromFile {
    param([string]$PidPath)

    if (-not (Test-Path $PidPath)) {
        return $null
    }

    $raw = (Get-Content -Path $PidPath -Raw).Trim()
    $pidValue = 0
    if ([int]::TryParse($raw, [ref]$pidValue)) {
        return $pidValue
    }

    return $null
}

function Stop-ManagedProcess {
    param([string]$Name)

    $pidPath = Join-Path $runDir "$Name.pid"
    $pidValue = Get-PidFromFile -PidPath $pidPath

    if ($pidValue) {
        try {
            Invoke-TaskKill -ProcessId $pidValue -Label $Name
        } catch {
            Write-Step "Skipping $Name cleanup: $($_.Exception.Message)"
        }
    }

    Remove-Item -Path $pidPath -Force -ErrorAction SilentlyContinue
}

function Stop-PortOwners {
    param([int]$Port)

    $pids = @()
    $lines = netstat -ano -p tcp | Select-String "LISTENING"
    foreach ($line in $lines) {
        $parts = [regex]::Split($line.ToString().Trim(), "\s+")
        if ($parts.Length -lt 5) {
            continue
        }

        if ($parts[1] -like "*:$Port") {
            $pidValue = 0
            if ([int]::TryParse($parts[-1], [ref]$pidValue) -and $pidValue -gt 0) {
                $pids += $pidValue
            }
        }
    }

    $pids | Sort-Object -Unique | ForEach-Object {
        try {
            Invoke-TaskKill -ProcessId $_ -Label "port $Port owner"
        } catch {
            Write-Step "Skipping port $Port cleanup: $($_.Exception.Message)"
        }
    }
}

function Stop-BackendPythonProcesses {
    # uv 管理的进程通过 PID 文件和端口清理，无需按 Python 路径匹配
}

function Test-TcpPort {
    param(
        [string]$Address,
        [int]$Port,
        [int]$TimeoutMs = 1000
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $asyncResult = $client.BeginConnect($Address, $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            return $false
        }

        $client.EndConnect($asyncResult) | Out-Null
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-Path {
    param(
        [string]$Path,
        [int]$TimeoutSeconds = 10
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $Path) {
            return $true
        }
        Start-Sleep -Milliseconds 200
    }

    return $false
}

function Wait-TcpPort {
    param(
        [string]$Address,
        [int]$Port,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort -Address $Address -Port $Port -TimeoutMs 1000) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }

    return $false
}

function Start-ServiceHost {
    param(
        [string]$Name,
        [string]$ScriptName
    )

    $pidPath = Join-Path $runDir "$Name.pid"
    $scriptPath = Join-Path $PSScriptRoot $ScriptName

    Remove-Item -Path $pidPath -Force -ErrorAction SilentlyContinue

    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-WindowStyle",
        $windowStyle,
        "-File",
        ('"{0}"' -f $scriptPath),
        "-RepoRoot",
        ('"{0}"' -f $repoRoot)
    ) -join " "

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "powershell.exe"
    $startInfo.Arguments = $arguments
    $startInfo.WorkingDirectory = $repoRoot
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = if ($ShowWindows) {
        [System.Diagnostics.ProcessWindowStyle]::Normal
    } else {
        [System.Diagnostics.ProcessWindowStyle]::Hidden
    }

    [System.Diagnostics.Process]::Start($startInfo) | Out-Null

    if (-not (Wait-Path -Path $pidPath -TimeoutSeconds 10)) {
        throw "Failed to start $Name."
    }

    $pidValue = Get-PidFromFile -PidPath $pidPath
    if (-not $pidValue) {
        throw "Failed to capture PID for $Name."
    }

    Write-Step "$Name started (PID $pidValue)."
}

New-Item -ItemType Directory -Force -Path $runDir, $logDir | Out-Null

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found in PATH. Install it from https://docs.astral.sh/uv/"
}
Assert-Path -Path $backendEnv -Message "Missing backend env file: $backendEnv"
Assert-Path -Path $nodeModules -Message "Missing frontend dependencies: $nodeModules"

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm.cmd was not found in PATH."
}

Write-Step "Closing existing services..."
Stop-ManagedProcess -Name "backend"
Stop-ManagedProcess -Name "frontend"
Stop-PortOwners -Port 8001
Stop-PortOwners -Port 5173
Stop-BackendPythonProcesses

Start-Sleep -Seconds 1

if ($StopOnly) {
    Write-Host ""
    Write-Step "Services stopped."
    return
}

if (-not (Test-TcpPort -Address "127.0.0.1" -Port 5433 -TimeoutMs 1000)) {
    throw "AI Slice PostgreSQL is not reachable on 127.0.0.1:5433. Run docker compose up -d postgres first."
}

$ffmpegBinDir = Find-FfmpegBinDir -Root $repoRoot
if ($ffmpegBinDir) {
    $env:PATH = "$ffmpegBinDir;$env:PATH"
    Write-Step "Using FFmpeg from $ffmpegBinDir"
}

$missingFfmpegTools = @()
if (-not (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue) -and -not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    $missingFfmpegTools += "ffmpeg"
}
if (-not (Get-Command ffprobe.exe -ErrorAction SilentlyContinue) -and -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    $missingFfmpegTools += "ffprobe"
}
if ($missingFfmpegTools.Count -gt 0) {
    Write-Step (
        (
            "Warning: missing {0}. Long audio transcription chunking and server-side clip/export features " +
            "will fail until FFmpeg is installed and added to PATH, or unpacked to tools/ffmpeg/bin."
        ) -f ($missingFfmpegTools -join ", ")
    )
}

try {
    Write-Step "Starting backend..."
    Start-ServiceHost -Name "backend" -ScriptName "run_backend.ps1"

    Write-Step "Starting frontend..."
    Start-ServiceHost -Name "frontend" -ScriptName "run_frontend.ps1"

    if (-not (Wait-TcpPort -Address "127.0.0.1" -Port 8001 -TimeoutSeconds 30)) {
        throw "Backend failed to open 127.0.0.1:8001. Check logs\backend.err.log"
    }

    if (-not (Wait-TcpPort -Address "127.0.0.1" -Port 5173 -TimeoutSeconds 30)) {
        throw "Frontend failed to open 127.0.0.1:5173. Check logs\frontend.err.log"
    }

    Write-Host ""
    Write-Step "Startup complete."
    Write-Host "Frontend (local): http://127.0.0.1:5173"
    Write-Host "Frontend (LAN):   http://192.168.110.221:5173"
    Write-Host "Backend (local):  http://127.0.0.1:8001"
    Write-Host "Health (local):   http://127.0.0.1:8001/api/health"
    Write-Host "Logs:              $logDir"
} catch {
    Write-Step "Startup failed. Cleaning up partial processes..."
    Stop-ManagedProcess -Name "backend"
    Stop-ManagedProcess -Name "frontend"
    throw
}
