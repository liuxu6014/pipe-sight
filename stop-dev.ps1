[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = $PSScriptRoot.ToLowerInvariant()
$RuntimeRoot = Join-Path $PSScriptRoot '.runtime\pipesight-dev'

function Stop-RecordedProcess {
    param(
        [string]$PidFile,
        [ValidateSet('Backend', 'Frontend')]
        [string]$Kind
    )

    if (-not (Test-Path -LiteralPath $PidFile)) {
        Write-Host "No recorded $Kind process."
        return
    }

    $processId = [int](Get-Content -Raw -LiteralPath $PidFile)
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "$Kind process is already stopped."
        return
    }

    $executable = ([string]$process.ExecutablePath).ToLowerInvariant()
    $commandLine = ([string]$process.CommandLine).ToLowerInvariant()
    $isOwned = $commandLine.Contains($RepoRoot)
    if ($Kind -eq 'Backend') {
        $isOwned = $isOwned -or $executable.StartsWith((Join-Path $RepoRoot 'backend\.venv').ToLowerInvariant())
    }

    if (-not $isOwned) {
        throw "Recorded PID $processId no longer clearly belongs to PipeSight; refusing to stop it. Process=$($process.Name), command=$($process.CommandLine)"
    }

    & taskkill.exe /PID $processId /T /F 2>$null | Out-Null
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "Stopped PipeSight $Kind (PID $processId)."
}

Stop-RecordedProcess -PidFile (Join-Path $RuntimeRoot 'frontend.pid') -Kind Frontend
Stop-RecordedProcess -PidFile (Join-Path $RuntimeRoot 'backend.pid') -Kind Backend
Write-Host 'PostgreSQL and Redis were left running intentionally.'
