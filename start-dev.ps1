[CmdletBinding()]
param(
    [ValidateSet('Auto', 'Local', 'Docker')]
    [string]$Infrastructure = 'Auto',

    [switch]$SkipInstall,
    [switch]$SkipDatabaseInit,
    [switch]$ForceDependencyInstall,

    [ValidateRange(1024, 65535)]
    [int]$BackendPort = 9099,

    [ValidateRange(1024, 65535)]
    [int]$FrontendPort = 5173
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Some Windows hosts expose both `Path` and `PATH`. PowerShell's Start-Process
# builds a case-insensitive environment dictionary and fails on that duplicate.
$processPath = [string]$env:Path
[System.Environment]::SetEnvironmentVariable('PATH', $null, [System.EnvironmentVariableTarget]::Process)
[System.Environment]::SetEnvironmentVariable('Path', $processPath, [System.EnvironmentVariableTarget]::Process)

$RepoRoot = $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot 'backend'
$FrontendRoot = Join-Path $RepoRoot 'frontend'
$BackendPython = Join-Path $BackendRoot '.venv\Scripts\python.exe'
$BackendApiModule = 'app.entrypoints.api'
$ViteEntry = Join-Path $FrontendRoot 'node_modules\vite\bin\vite.js'
$RuntimeRoot = Join-Path $RepoRoot '.runtime\pipesight-dev'
$BackendPidFile = Join-Path $RuntimeRoot 'backend.pid'
$FrontendPidFile = Join-Path $RuntimeRoot 'frontend.pid'
$SessionId = '{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $PID
$BackendStdout = Join-Path $RuntimeRoot "backend-$SessionId.out.log"
$BackendStderr = Join-Path $RuntimeRoot "backend-$SessionId.err.log"
$FrontendStdout = Join-Path $RuntimeRoot "frontend-$SessionId.out.log"
$FrontendStderr = Join-Path $RuntimeRoot "frontend-$SessionId.err.log"

New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
$env:UV_CACHE_DIR = Join-Path $RuntimeRoot 'uv-cache'
New-Item -ItemType Directory -Path $env:UV_CACHE_DIR -Force | Out-Null

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Assert-Command {
    param(
        [string]$Name,
        [string]$InstallHint
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "Required command '$Name' was not found. $InstallHint"
    }
    return $command.Source
}

function Test-TcpPort {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMilliseconds = 800
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connectTask = $client.ConnectAsync($HostName, $Port)
        if (-not $connectTask.Wait($TimeoutMilliseconds)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Select-AvailableFrontendPort {
    param([int]$PreferredPort)

    $candidate = $PreferredPort
    while ($candidate -le 65535 -and (Test-TcpPort -HostName '127.0.0.1' -Port $candidate)) {
        $candidate++
    }
    if ($candidate -gt 65535) {
        throw "No available frontend port found after $PreferredPort."
    }
    return $candidate
}

function Wait-TcpPort {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort -HostName $HostName -Port $Port) {
            return
        }
        Start-Sleep -Milliseconds 750
    }
    throw "Timed out waiting for ${HostName}:$Port."
}

function Test-HttpEndpoint {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 4
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Test-PipeSightBackend {
    param([string]$BaseUrl)

    try {
        $openApi = Invoke-RestMethod -Uri "$BaseUrl/openapi.json" -TimeoutSec 5
        $registeredPaths = @($openApi.paths.PSObject.Properties.Name)
        $requiredPaths = @(
            '/pipeline/dashboard',
            '/pipeline/workspace',
            '/pipeline/research/jobs',
            '/pipeline/research/reports',
            '/pipeline/research/reports/{report_id}/diagram',
            '/pipeline/research/reports/{report_id}/versions/{version_no}/restore'
        )
        return @($requiredPaths | Where-Object { $registeredPaths -notcontains $_ }).Count -eq 0
    }
    catch {
        return $false
    }
}

function Get-PortOwners {
    param([int]$Port)

    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($listener in @($listeners)) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            [pscustomobject]@{
                Id = [int]$listener.OwningProcess
                Name = [string]$process.Name
                ExecutablePath = [string]$process.ExecutablePath
                CommandLine = [string]$process.CommandLine
            }
        }
    }
}

function Test-OwnedProcess {
    param(
        [pscustomobject]$ProcessInfo,
        [ValidateSet('Backend', 'Frontend')]
        [string]$Kind
    )

    $repo = $RepoRoot.ToLowerInvariant()
    $backend = $BackendRoot.ToLowerInvariant()
    $frontend = $FrontendRoot.ToLowerInvariant()
    $executable = ([string]$ProcessInfo.ExecutablePath).ToLowerInvariant()
    $commandLine = ([string]$ProcessInfo.CommandLine).ToLowerInvariant()

    if ($Kind -eq 'Backend') {
        return (
            $executable.StartsWith((Join-Path $backend '.venv').ToLowerInvariant()) -or
            $commandLine.Contains($backend) -or
            ($commandLine.Contains($repo) -and $commandLine.Contains('app.entrypoints.api'))
        )
    }

    return (
        $commandLine.Contains($frontend) -or
        ($commandLine.Contains($repo) -and $commandLine.Contains('vite'))
    )
}

function Stop-ProcessTree {
    param([int]$RootProcessId)

    if ($null -ne (Get-Process -Id $RootProcessId -ErrorAction SilentlyContinue)) {
        & taskkill.exe /PID $RootProcessId /T /F 2>$null | Out-Null
    }
}

function Clear-RecordedProcess {
    param(
        [string]$PidFile,
        [ValidateSet('Backend', 'Frontend')]
        [string]$Kind
    )

    if (-not (Test-Path -LiteralPath $PidFile)) {
        return
    }

    $recordedValue = (Get-Content -Raw -LiteralPath $PidFile -ErrorAction SilentlyContinue).Trim()
    $recordedProcessId = 0
    if (-not [int]::TryParse($recordedValue, [ref]$recordedProcessId)) {
        Remove-Item -LiteralPath $PidFile -Force
        return
    }

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $recordedProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $PidFile -Force
        return
    }

    if (-not (Test-OwnedProcess -ProcessInfo $process -Kind $Kind)) {
        throw "Recorded PID $recordedProcessId no longer clearly belongs to PipeSight; refusing to stop it. Process=$($process.Name), command=$($process.CommandLine)"
    }

    Write-Host "Stopping previously recorded PipeSight $Kind process tree (PID $recordedProcessId)..." -ForegroundColor Yellow
    Stop-ProcessTree -RootProcessId $recordedProcessId
    Remove-Item -LiteralPath $PidFile -Force
}

function Clear-OwnedPort {
    param(
        [int]$Port,
        [ValidateSet('Backend', 'Frontend')]
        [string]$Kind
    )

    $deadline = (Get-Date).AddSeconds(12)
    $sawOwnedListener = $false
    $quietSince = $null
    while ((Get-Date) -lt $deadline) {
        $owners = @(Get-PortOwners -Port $Port)
        if ($owners.Count -eq 0) {
            if (-not $sawOwnedListener) {
                return
            }
            if ($null -eq $quietSince) {
                $quietSince = Get-Date
            }
            if (((Get-Date) - $quietSince).TotalSeconds -ge 2) {
                return
            }
        }
        else {
            $quietSince = $null
            foreach ($owner in $owners) {
                if (-not (Test-OwnedProcess -ProcessInfo $owner -Kind $Kind)) {
                    $details = "PID=$($owner.Id), process=$($owner.Name), executable=$($owner.ExecutablePath), command=$($owner.CommandLine)"
                    throw "Port $Port is occupied by a process that does not clearly belong to PipeSight. Refusing to stop it. $details"
                }
            }
            foreach ($owner in $owners) {
                $sawOwnedListener = $true
                Write-Host "Stopping stale PipeSight $Kind listener on port $Port (PID $($owner.Id))..." -ForegroundColor Yellow
                Stop-Process -Id $owner.Id -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Milliseconds 300
    }
    throw "The previous PipeSight process did not keep port $Port released."
}

function Get-CombinedHash {
    param([string[]]$Paths)

    $hashes = foreach ($path in $Paths) {
        (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($hashes -join ':'))
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
}

function Ensure-BackendDependencies {
    param([string]$UvPath)

    $requirementsPath = Join-Path $BackendRoot 'requirements-pg.txt'
    $pyprojectPath = Join-Path $BackendRoot 'pyproject.toml'
    $stampPath = Join-Path $BackendRoot '.venv\.pipesight-dependencies.sha256'
    $expectedHash = Get-CombinedHash -Paths @($requirementsPath, $pyprojectPath)
    $needsInstall = $ForceDependencyInstall.IsPresent

    if (-not (Test-Path -LiteralPath $BackendPython)) {
        $needsInstall = $true
        Write-Host 'Creating backend virtual environment with uv...'
        Push-Location $BackendRoot
        try {
            & $UvPath venv .venv
            if ($LASTEXITCODE -ne 0) {
                throw 'uv failed to create backend/.venv.'
            }
        }
        finally {
            Pop-Location
        }
    }

    if (-not $needsInstall) {
        # A missing module writes a traceback to stderr. With
        # $ErrorActionPreference=Stop, PowerShell turns that diagnostic into
        # an exception before we can decide to install dependencies.
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & $BackendPython -c "import uvicorn, fastapi, asyncpg, redis" *> $null
            $dependencyCheckFailed = $LASTEXITCODE -ne 0
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($dependencyCheckFailed) {
            $needsInstall = $true
        }
    }

    if (-not $needsInstall) {
        $needsInstall = -not (Test-Path -LiteralPath $stampPath) -or
            ((Get-Content -Raw -LiteralPath $stampPath -ErrorAction SilentlyContinue).Trim() -ne $expectedHash)
    }

    if ($SkipInstall -and $needsInstall) {
        throw 'Backend dependencies are missing or out of date, but -SkipInstall was supplied. Run without -SkipInstall once.'
    }

    if ($needsInstall) {
        Write-Host 'Installing backend requirements with uv (first run may take several minutes)...'
        Push-Location $BackendRoot
        try {
            & $UvPath pip install --python $BackendPython -r requirements-pg.txt
            if ($LASTEXITCODE -ne 0) {
                throw 'uv failed to install backend/requirements-pg.txt.'
            }
        }
        finally {
            Pop-Location
        }
    }

    & $BackendPython -c "import uvicorn, fastapi, asyncpg, redis"
    if ($LASTEXITCODE -ne 0) {
        throw 'Backend dependency verification failed; uvicorn or another runtime dependency is still unavailable.'
    }
    Set-Content -LiteralPath $stampPath -Value $expectedHash -Encoding ascii
}

function Ensure-FrontendDependencies {
    param([string]$NpmPath)

    $packageLockPath = Join-Path $FrontendRoot 'package-lock.json'
    $vitePath = Join-Path $FrontendRoot 'node_modules\.bin\vite.cmd'
    $stampPath = Join-Path $FrontendRoot 'node_modules\.pipesight-package-lock.sha256'
    $expectedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $packageLockPath).Hash
    $needsInstall = $ForceDependencyInstall.IsPresent -or -not (Test-Path -LiteralPath $vitePath)

    if (-not $needsInstall) {
        $needsInstall = -not (Test-Path -LiteralPath $stampPath) -or
            ((Get-Content -Raw -LiteralPath $stampPath -ErrorAction SilentlyContinue).Trim() -ne $expectedHash)
    }

    if ($SkipInstall -and $needsInstall) {
        throw 'Frontend dependencies are missing or out of date, but -SkipInstall was supplied. Run without -SkipInstall once.'
    }

    if ($needsInstall) {
        Write-Host 'Installing frontend dependencies with npm ci (first run may take several minutes)...'
        Push-Location $FrontendRoot
        try {
            & $NpmPath ci
            if ($LASTEXITCODE -ne 0) {
                throw 'npm ci failed.'
            }
        }
        finally {
            Pop-Location
        }
    }

    if (-not (Test-Path -LiteralPath $vitePath)) {
        throw 'Frontend dependency verification failed; Vite is unavailable.'
    }
    Set-Content -LiteralPath $stampPath -Value $expectedHash -Encoding ascii
}

function Get-DotEnvValue {
    param(
        [string]$Name,
        [string]$DefaultValue
    )

    $envPath = Join-Path $BackendRoot '.env.dev'
    $escapedName = [System.Text.RegularExpressions.Regex]::Escape($Name)
    foreach ($line in Get-Content -LiteralPath $envPath) {
        if ($line -match "^\s*$escapedName\s*=\s*(.*?)\s*$") {
            $value = $Matches[1].Trim()
            if ($value.Length -ge 2) {
                $first = $value.Substring(0, 1)
                $last = $value.Substring($value.Length - 1, 1)
                if (($first -eq "'" -and $last -eq "'") -or ($first -eq '"' -and $last -eq '"')) {
                    return $value.Substring(1, $value.Length - 2)
                }
            }
            return $value
        }
    }
    return $DefaultValue
}

function Test-DockerEngine {
    param([string]$DockerPath)

    $stdoutPath = Join-Path $RuntimeRoot "docker-info-$SessionId.out.log"
    $stderrPath = Join-Path $RuntimeRoot "docker-info-$SessionId.err.log"
    $startArguments = @{
        FilePath = $DockerPath
        ArgumentList = @('info', '--format', '{{.ServerVersion}}')
        RedirectStandardOutput = $stdoutPath
        RedirectStandardError = $stderrPath
        WindowStyle = 'Hidden'
        PassThru = $true
    }
    $process = Start-Process @startArguments
    if (-not $process.WaitForExit(10000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        return $false
    }
    return $process.ExitCode -eq 0
}

function Start-DockerInfrastructure {
    param([string]$DockerPath)

    Write-Host 'Local PostgreSQL/Redis are not both available; starting Docker infrastructure...'
    if (-not (Test-DockerEngine -DockerPath $DockerPath)) {
        throw 'Docker is installed but the Docker engine is not running. Start Docker Desktop and retry, or use -Infrastructure Local.'
    }

    & $DockerPath compose -p pipesight-pg -f (Join-Path $RepoRoot 'docker-compose.pg.yml') up -d ruoyi-pg ruoyi-redis
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose failed to start PostgreSQL and Redis.'
    }

    Wait-TcpPort -HostName '127.0.0.1' -Port 15432 -TimeoutSeconds 90
    Wait-TcpPort -HostName '127.0.0.1' -Port 16379 -TimeoutSeconds 60

    $env:DB_TYPE = 'postgresql'
    $env:DB_HOST = '127.0.0.1'
    $env:DB_PORT = '15432'
    $env:DB_USERNAME = 'postgres'
    $composeDbPassword = Get-DotEnvValue -Name 'POSTGRES_PASSWORD' -DefaultValue (Get-DotEnvValue -Name 'DB_PASSWORD' -DefaultValue 'root')
    $env:DB_PASSWORD = $composeDbPassword
    $env:DB_DATABASE = 'ruoyi-fastapi'
    $env:INSIGHTHUB_DB_TYPE = 'postgresql'
    $env:INSIGHTHUB_DB_HOST = '127.0.0.1'
    $env:INSIGHTHUB_DB_PORT = '15432'
    $env:INSIGHTHUB_DB_USERNAME = 'postgres'
    $env:INSIGHTHUB_DB_PASSWORD = $composeDbPassword
    $env:INSIGHTHUB_DB_DATABASE = 'ruoyi-fastapi'
    $env:INSIGHTHUB_DB_SCHEMA = 'news'
    $env:REDIS_HOST = '127.0.0.1'
    $env:REDIS_PORT = '16379'
    $env:REDIS_USERNAME = ''
    $env:REDIS_PASSWORD = ''
    $env:REDIS_DATABASE = '2'
}

function Use-LocalInfrastructure {
    $databasePort = [int](Get-DotEnvValue -Name 'DB_PORT' -DefaultValue '5432')
    $redisPort = [int](Get-DotEnvValue -Name 'REDIS_PORT' -DefaultValue '6379')
    if (-not (Test-TcpPort -HostName '127.0.0.1' -Port $databasePort)) {
        throw "PostgreSQL is not listening on 127.0.0.1:$databasePort. Start it or use -Infrastructure Docker."
    }
    if (-not (Test-TcpPort -HostName '127.0.0.1' -Port $redisPort)) {
        throw "Redis is not listening on 127.0.0.1:$redisPort. Start it or use -Infrastructure Docker."
    }

    $databaseType = Get-DotEnvValue -Name 'DB_TYPE' -DefaultValue 'postgresql'
    if ($databaseType -ne 'postgresql') {
        throw "The one-click local initializer targets PostgreSQL, but backend/.env.dev has DB_TYPE=$databaseType. Use PostgreSQL configuration."
    }

    $env:DB_TYPE = $databaseType
    $env:DB_HOST = Get-DotEnvValue -Name 'DB_HOST' -DefaultValue '127.0.0.1'
    $env:DB_PORT = [string]$databasePort
    $env:DB_USERNAME = Get-DotEnvValue -Name 'DB_USERNAME' -DefaultValue 'postgres'
    $env:DB_PASSWORD = Get-DotEnvValue -Name 'DB_PASSWORD' -DefaultValue 'root'
    $env:DB_DATABASE = Get-DotEnvValue -Name 'DB_DATABASE' -DefaultValue 'ruoyi-fastapi'
    $env:REDIS_HOST = Get-DotEnvValue -Name 'REDIS_HOST' -DefaultValue '127.0.0.1'
    $env:REDIS_PORT = [string]$redisPort
    $env:REDIS_USERNAME = Get-DotEnvValue -Name 'REDIS_USERNAME' -DefaultValue ''
    $env:REDIS_PASSWORD = Get-DotEnvValue -Name 'REDIS_PASSWORD' -DefaultValue ''
    $env:REDIS_DATABASE = Get-DotEnvValue -Name 'REDIS_DATABASE' -DefaultValue '2'
}

function Initialize-Database {
    $baseSql = Join-Path $BackendRoot 'sql\ruoyi-fastapi-pg.sql'
    $pipelineSql = Join-Path $BackendRoot 'sql\pipeline-domain-pg.sql'
    $pipelineEnhancementSql = Join-Path $BackendRoot 'sql\pipeline-domain-enhancement-pg.sql'
    $insightHubSql = Join-Path $RepoRoot 'backend\sql\insighthub-schema.pg.sql'
    $initScriptPath = Join-Path $RuntimeRoot 'initialize_postgresql.py'
    $initCode = @'
import asyncio
import os
import re
import sys
from pathlib import Path

import asyncpg


async def execute_sql(connection, path: str) -> None:
    sql = Path(path).read_text(encoding="utf-8-sig")
    # asyncpg executes SQL directly and does not understand psql meta-commands.
    sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("\\"))
    await connection.execute(sql)


database = os.environ["DB_DATABASE"]
if not re.fullmatch(r"[A-Za-z0-9_-]+", database):
    raise SystemExit(f"Unsafe database name: {database!r}")

async def main() -> None:
    connect_args = dict(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USERNAME"],
        password=os.environ.get("DB_PASSWORD", ""),
    )
    admin = await asyncpg.connect(database="postgres", **connect_args)
    try:
        exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", database)
        if not exists:
            await admin.execute('CREATE DATABASE "' + database.replace('"', '""') + '"')
    finally:
        await admin.close()

    connection = await asyncpg.connect(database=database, **connect_args)
    try:
        has_base_tables = await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'sys_user')"
        )
        if not has_base_tables:
            print("Base RuoYi tables are missing; importing ruoyi-fastapi-pg.sql...")
            await execute_sql(connection, sys.argv[1])
        if not has_base_tables:
            print("Applying PipeSight baseline tables before Alembic migrations...")
            await execute_sql(connection, sys.argv[2])
            await execute_sql(connection, sys.argv[3])
        if len(sys.argv) > 4 and Path(sys.argv[4]).exists():
            print("Applying InsightHub PostgreSQL schema...")
            await execute_sql(connection, sys.argv[4])
    finally:
        await connection.close()


asyncio.run(main())
'@

    [System.IO.File]::WriteAllText($initScriptPath, $initCode, [System.Text.UTF8Encoding]::new($false))
    & $BackendPython $initScriptPath $baseSql $pipelineSql $pipelineEnhancementSql $insightHubSql
    if ($LASTEXITCODE -ne 0) {
        throw "Database initialization failed for $($env:DB_HOST):$($env:DB_PORT)/$($env:DB_DATABASE). Check credentials in backend/.env.dev or Docker health."
    }
    Push-Location $BackendRoot
    try {
        & $BackendPython -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            throw 'Database migrations failed; backend startup has been stopped.'
        }
    } finally {
        Pop-Location
    }
}

function Show-LogTail {
    param([string[]]$Paths)

    foreach ($path in $Paths) {
        if (Test-Path -LiteralPath $path) {
            Write-Host "--- $path"
            Get-Content -LiteralPath $path -Tail 40
        }
    }
}

function Wait-HttpProcess {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Url,
        [int]$TimeoutSeconds,
        [string[]]$LogPaths
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) {
            Show-LogTail -Paths $LogPaths
            throw "Process exited before $Url became available (exit code $($Process.ExitCode))."
        }
        $response = $null
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
        }
        catch {
            $response = $null
        }
        if ($null -ne $response -and $response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            Start-Sleep -Milliseconds 500
            $Process.Refresh()
            if ($Process.HasExited) {
                Show-LogTail -Paths $LogPaths
                throw "Process exited immediately after $Url responded (exit code $($Process.ExitCode))."
            }
            return
        }
        Start-Sleep -Milliseconds 750
    }

    Show-LogTail -Paths $LogPaths
    throw "Timed out waiting for $Url."
}

$startLock = $null
try {
try {
    $startLockPath = Join-Path $RuntimeRoot 'start.lock'
    $startLock = [System.IO.File]::Open(
        $startLockPath,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
}
catch [System.IO.IOException] {
    throw 'Another PipeSight startup is already running. Wait for it to finish or stop it before retrying.'
}

Write-Step 'Checking developer tools'
$uvPath = Assert-Command -Name 'uv' -InstallHint 'Install uv from https://docs.astral.sh/uv/.'
$npmPath = Assert-Command -Name 'npm.cmd' -InstallHint 'Install Node.js 18 or newer.'
$nodePath = Assert-Command -Name 'node.exe' -InstallHint 'Install Node.js 18 or newer.'

Write-Step 'Preparing dependencies'
Ensure-BackendDependencies -UvPath $uvPath
Ensure-FrontendDependencies -NpmPath $npmPath

Write-Step 'Checking PostgreSQL and Redis'
$localDatabasePort = [int](Get-DotEnvValue -Name 'DB_PORT' -DefaultValue '5432')
$localRedisPort = [int](Get-DotEnvValue -Name 'REDIS_PORT' -DefaultValue '6379')
$useDocker = $Infrastructure -eq 'Docker'
if ($Infrastructure -eq 'Auto') {
    $useDocker = -not (
        (Test-TcpPort -HostName '127.0.0.1' -Port $localDatabasePort) -and
        (Test-TcpPort -HostName '127.0.0.1' -Port $localRedisPort)
    )
}

if ($useDocker) {
    $dockerPath = Assert-Command -Name 'docker' -InstallHint 'Install Docker Desktop, or start local PostgreSQL and Redis and use -Infrastructure Local.'
    Start-DockerInfrastructure -DockerPath $dockerPath
}
else {
    Use-LocalInfrastructure
}
Write-Host "Using PostgreSQL at $($env:DB_HOST):$($env:DB_PORT) and Redis at $($env:REDIS_HOST):$($env:REDIS_PORT)."

if (-not $SkipDatabaseInit) {
    Write-Step 'Initializing database tables'
    Initialize-Database
}

Write-Step 'Checking application ports'
$backendBaseUrl = "http://127.0.0.1:$BackendPort"
$frontendBaseUrl = "http://127.0.0.1:$FrontendPort"
if (
    $BackendPort -eq 9099 -and
    (Test-HttpEndpoint -Url "$backendBaseUrl/openapi.json") -and
    -not (Test-PipeSightBackend -BaseUrl $backendBaseUrl)
) {
    $BackendPort = 9100
    $backendBaseUrl = "http://127.0.0.1:$BackendPort"
    Write-Host 'Port 9099 is serving an outdated PipeSight API; switching this session to port 9100.' -ForegroundColor Yellow
}
$reuseBackend = Test-PipeSightBackend -BaseUrl $backendBaseUrl
$reuseFrontend = $BackendPort -eq 9099 -and $FrontendPort -eq 5173 -and (Test-HttpEndpoint -Url "$frontendBaseUrl/login")
if (-not $reuseFrontend -and (Test-TcpPort -HostName '127.0.0.1' -Port $FrontendPort)) {
    $requestedFrontendPort = $FrontendPort
    $FrontendPort = Select-AvailableFrontendPort -PreferredPort ($FrontendPort + 1)
    $frontendBaseUrl = "http://127.0.0.1:$FrontendPort"
    Write-Host "Frontend port $requestedFrontendPort is occupied; using port $FrontendPort for this session." -ForegroundColor Yellow
}
if ($reuseBackend) {
    Write-Host "A healthy PipeSight backend is already available on port $BackendPort; reusing it." -ForegroundColor Yellow
}
else {
    Clear-RecordedProcess -PidFile $BackendPidFile -Kind Backend
    Clear-OwnedPort -Port $BackendPort -Kind Backend
}
if ($reuseFrontend) {
    Write-Host "A healthy PipeSight frontend is already available on port $FrontendPort; reusing it." -ForegroundColor Yellow
}
else {
    Clear-RecordedProcess -PidFile $FrontendPidFile -Kind Frontend
    Clear-OwnedPort -Port $FrontendPort -Kind Frontend
}

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:APP_PORT = [string]$BackendPort
$env:VITE_BACKEND_TARGET = $backendBaseUrl
$env:BROWSER = 'none'

$backendProcess = $null
$frontendProcess = $null
try {
    if (-not $reuseBackend) {
        Write-Step 'Starting backend with uv'
        $backendStartArguments = @{
            FilePath = $uvPath
            ArgumentList = @('run', '--project', $BackendRoot, '--no-sync', 'python', '-m', $BackendApiModule, '--env=dev')
            WorkingDirectory = $BackendRoot
            Environment = @{ PYTHONPATH = "$(Join-Path $BackendRoot 'src');$BackendRoot" }
            RedirectStandardOutput = $BackendStdout
            RedirectStandardError = $BackendStderr
            WindowStyle = 'Hidden'
            PassThru = $true
        }
        $backendProcess = Start-Process @backendStartArguments
        Set-Content -LiteralPath $BackendPidFile -Value $backendProcess.Id -Encoding ascii
        Wait-HttpProcess -Process $backendProcess -Url "$backendBaseUrl/openapi.json" -TimeoutSeconds 90 -LogPaths @($BackendStderr, $BackendStdout)
    }

    if (-not $reuseFrontend) {
        Write-Step 'Starting frontend with Vite'
        $frontendStartArguments = @{
            FilePath = $nodePath
            ArgumentList = @($ViteEntry, '--host', '127.0.0.1', '--port', [string]$FrontendPort, '--strictPort')
            WorkingDirectory = $FrontendRoot
            RedirectStandardOutput = $FrontendStdout
            RedirectStandardError = $FrontendStderr
            WindowStyle = 'Hidden'
            PassThru = $true
        }
        $frontendProcess = Start-Process @frontendStartArguments
        Set-Content -LiteralPath $FrontendPidFile -Value $frontendProcess.Id -Encoding ascii
        Wait-HttpProcess -Process $frontendProcess -Url "$frontendBaseUrl/portal" -TimeoutSeconds 60 -LogPaths @($FrontendStderr, $FrontendStdout)
    }
}
catch {
    if ($null -ne $frontendProcess) {
        Stop-ProcessTree -RootProcessId $frontendProcess.Id
        Remove-Item -LiteralPath $FrontendPidFile -Force -ErrorAction SilentlyContinue
    }
    if ($null -ne $backendProcess) {
        Stop-ProcessTree -RootProcessId $backendProcess.Id
        Remove-Item -LiteralPath $BackendPidFile -Force -ErrorAction SilentlyContinue
    }
    throw
}

Write-Host "`nPipeSight is ready." -ForegroundColor Green
Write-Host "Frontend: $frontendBaseUrl/portal"
Write-Host "Backend:  $backendBaseUrl/docs"
Write-Host "Logs:     $RuntimeRoot"
Write-Host 'Stop:     powershell -ExecutionPolicy Bypass -File .\stop-dev.ps1'
}
finally {
    if ($null -ne $startLock) {
        $startLock.Dispose()
    }
}
