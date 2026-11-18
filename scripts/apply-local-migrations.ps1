<#
.SYNOPSIS
Applies the Supabase SQL migrations to the isolated local PostgreSQL cluster.
Local-only auth emulation is applied first, then migrations, seed and assertions.
#>
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$conn = @('-h', '127.0.0.1', '-p', '55432', '-U', 'postgres', '-d', 'blood_registry', '-v', 'ON_ERROR_STOP=1')

function Invoke-SqlFile([string]$relativePath) {
    $full = Join-Path $repo $relativePath
    Write-Output "-- applying $relativePath"
    & $psql @conn -f $full
    if ($LASTEXITCODE -ne 0) { throw "Failed to apply $relativePath" }
}

Invoke-SqlFile 'supabase\local\0000_auth_emulation.sql'
foreach ($file in (Get-ChildItem (Join-Path $repo 'supabase\migrations') -Filter '*.sql' | Sort-Object Name)) {
    Invoke-SqlFile $file.FullName.Replace($repo + '\', '')
}
Invoke-SqlFile 'supabase\seed.sql'
Invoke-SqlFile 'supabase\local\seed_auth_users.sql'
Invoke-SqlFile 'supabase\tests\verify_database.sql'
Write-Output 'LOCAL DATABASE READY'
