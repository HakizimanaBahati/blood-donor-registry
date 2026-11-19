<#
.SYNOPSIS
Manages an isolated PostgreSQL cluster used ONLY for local development and tests.

.DESCRIPTION
This does NOT touch the PostgreSQL service already installed on the machine.
It creates a throwaway cluster in .local-pg/ on port 55432 with trust auth so the
SQL migrations and Django tests can be executed without any external credentials.

On Windows the cluster is started through a dedicated Windows service running as
NetworkService. PostgreSQL refuses to run under an elevated token, and a service
also keeps the server alive after the invoking shell exits.

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
$serviceName = 'BDRLocalPG'
$serviceAccount = 'NT AUTHORITY\NetworkService'
$serviceAcl = 'NT AUTHORITY\NETWORK SERVICE:(OI)(CI)F'

function Get-LocalService {
    Get-Service -Name $serviceName -ErrorAction SilentlyContinue
}

function Test-Running {
    # A dead server can leave a LISTENING socket behind briefly on Windows.
    # Prove the server actually answers instead of trusting the port state.
    $previous = $ErrorActionPreference
    $previousTimeout = $env:PGCONNECT_TIMEOUT
    $ErrorActionPreference = 'SilentlyContinue'
    $env:PGCONNECT_TIMEOUT = '2'
    & "$binDir\psql.exe" -h 127.0.0.1 -p $port -U postgres -d postgres -Atc 'SELECT 1;' 2>&1 | Out-Null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    $env:PGCONNECT_TIMEOUT = $previousTimeout
    return $code -eq 0
}

function Initialize-Cluster {
    if (-not (Test-Path (Join-Path $dataDir 'PG_VERSION'))) {
        New-Item -ItemType Directory -Force -Path (Split-Path $dataDir) | Out-Null
        & "$binDir\initdb.exe" -D $dataDir -U postgres -A trust --encoding=UTF8 --locale=C | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
        Write-Output "Initialised local cluster at $dataDir"
    }

    # The service account must be able to read and write the data directory.
    icacls (Join-Path $RepoRoot '.local-pg') /grant $serviceAcl | Out-Null

    if (-not (Get-LocalService)) {
        & "$binDir\pg_ctl.exe" register -N $serviceName -D $dataDir -U $serviceAccount -P '' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not register the local PostgreSQL service' }
        # pg_ctl register drops -o options on Windows; add them to ImagePath directly.
        $imagePath = '"{0}\pg_ctl.exe" runservice -N "{1}" -D "{2}" -o "-p {3} -h 127.0.0.1" -w' -f $binDir, $serviceName, $dataDir, $port
        Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\$serviceName" -Name ImagePath -Value $imagePath
        Write-Output "Registered Windows service $serviceName on port $port"
    }
}

function Ensure-Database {
    $exists = & "$binDir\psql.exe" -h 127.0.0.1 -p $port -U postgres -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = 'blood_registry';"
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect local databases' }
    if (-not ($exists -eq '1')) {
        & "$binDir\createdb.exe" -h 127.0.0.1 -p $port -U postgres blood_registry | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not create blood_registry database' }
        Write-Output 'Created local database blood_registry'
    }
}

switch ($Action) {
    'reset' {
        if (Test-Running) {
            $service = Get-LocalService
            if ($service) { Stop-Service -Name $serviceName -Force } else { & "$binDir\pg_ctl.exe" -D $dataDir stop -m fast | Out-Null }
        }
        if (Test-Path (Join-Path $RepoRoot '.local-pg')) {
            Remove-Item -Recurse -Force (Join-Path $RepoRoot '.local-pg')
        }
        Write-Output "Removed $dataDir"
    }
    'start' {
        if (-not (Test-Path $binDir)) { throw "PostgreSQL 18 binaries not found at $binDir. Edit scripts/local-db.ps1." }
        Initialize-Cluster
        if (-not (Test-Running)) {
            $service = Get-LocalService
            if ($service) {
                Start-Service -Name $serviceName
            } else {
                # Fallback for non-Windows-service setups: start directly as this user.
                New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null
                $args = "-D `"$dataDir`" -p $port -h 127.0.0.1"
                Start-Process -FilePath "$binDir\postgres.exe" -ArgumentList $args `
                    -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" `
                    -WindowStyle Hidden | Out-Null
            }
            for ($i = 0; $i -lt 80 -and -not (Test-Running); $i++) { Start-Sleep -Milliseconds 250 }
            if (-not (Test-Running)) { throw 'postgres failed to start; check the PostgreSQL event log' }
        }
        Write-Output "Local PostgreSQL listening on 127.0.0.1:$port"
        Ensure-Database
        & "$binDir\psql.exe" -h 127.0.0.1 -p $port -U postgres -d postgres -Atc 'SELECT version();'
    }
    'stop' {
        if (Test-Running) {
            $service = Get-LocalService
            if ($service) { Stop-Service -Name $serviceName -Force } else { & "$binDir\pg_ctl.exe" -D $dataDir stop -m fast | Out-Null }
            Write-Output 'Local PostgreSQL stopped.'
        } else { Write-Output 'Local PostgreSQL was not running.' }
    }
    'psql' {
        if (-not (Test-Running)) { throw 'Local PostgreSQL is not running. Run with -Action start first.' }
        & "$binDir\psql.exe" -h 127.0.0.1 -p $port -U postgres -d blood_registry
    }
}
