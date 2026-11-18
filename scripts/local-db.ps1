<#
.SYNOPSIS
Manages an isolated PostgreSQL cluster used ONLY for local development and tests.

.DESCRIPTION
This does NOT touch the PostgreSQL service already installed on the machine.
It creates a throwaway cluster in .local-pg/ on port 55432 with trust auth so the
SQL migrations and Django tests can be executed without any external credentials.

Usage:
  .\scripts\local-db.ps1 start     # initialise (once) and start
  .\scripts\local-db.ps1 stop      # stop the cluster
  .\scripts\local-db.ps1 reset     # delete the cluster and start fresh
  .\scripts\local-db.ps1 psql      # open a psql shell
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('start', 'stop', 'reset', 'psql')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $RepoRoot '.local-pg\data'
$logFile = Join-Path $RepoRoot '.local-pg\postgres.log'
$binDir = 'C:\Program Files\PostgreSQL\18\bin'
$port = 55432

function Test-Running {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return [bool]$conn
}

switch ($Action) {
    'reset' {
        if (Test-Running) { & "$binDir\pg_ctl.exe" -D $dataDir stop -m fast | Out-Null }
        if (Test-Path (Join-Path $RepoRoot '.local-pg')) {
            Remove-Item -Recurse -Force (Join-Path $RepoRoot '.local-pg')
        }
        Write-Output "Removed $dataDir"
    }
    'start' {
        if (-not (Test-Path $binDir)) { throw "PostgreSQL 18 binaries not found at $binDir. Edit scripts/local-db.ps1." }
        if (-not (Test-Path (Join-Path $dataDir 'PG_VERSION'))) {
            New-Item -ItemType Directory -Force -Path (Split-Path $dataDir) | Out-Null
            & "$binDir\initdb.exe" -D $dataDir -U postgres -A trust --encoding=UTF8 --locale=C | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
            Write-Output "Initialised local cluster at $dataDir"
        }
        if (-not (Test-Running)) {
            New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null
            # Start postgres.exe directly: pg_ctl.exe keeps the PowerShell output pipe
            # open on Windows, which makes a tool call appear to hang.
            $args = "-D `"$dataDir`" -p $port -h 127.0.0.1"
            Start-Process -FilePath "$binDir\postgres.exe" -ArgumentList $args `
                -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" `
                -WindowStyle Hidden | Out-Null
            for ($i = 0; $i -lt 40 -and -not (Test-Running); $i++) { Start-Sleep -Milliseconds 250 }
            if (-not (Test-Running)) { throw 'postgres failed to start; check .local-pg/postgres.log.err' }
        }
        Write-Output "Local PostgreSQL listening on 127.0.0.1:$port"
        & "$binDir\psql.exe" -h 127.0.0.1 -p $port -U postgres -d postgres -Atc 'SELECT version();'
    }
    'stop' {
        if (Test-Running) {
            & "$binDir\pg_ctl.exe" -D $dataDir stop -m fast | Out-Null
            Write-Output 'Local PostgreSQL stopped.'
        } else { Write-Output 'Local PostgreSQL was not running.' }
    }
    'psql' {
        if (-not (Test-Running)) { throw 'Local PostgreSQL is not running. Run with -Action start first.' }
        & "$binDir\psql.exe" -h 127.0.0.1 -p $port -U postgres -d blood_registry
    }
}
