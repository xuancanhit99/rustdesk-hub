[CmdletBinding()]
param(
    [switch] $PurgeData,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')

Initialize-RustDeskEnv
Assert-DockerCli
Assert-DockerDaemon
$compose = Get-ComposePrefix

if ($PurgeData) {
    if (-not $Force) { throw 'Data purge requires both -PurgeData and -Force.' }
    & docker @compose down --remove-orphans --volumes
    if ($LASTEXITCODE -ne 0) { throw 'Failed to stop RustDesk Hub.' }
    Write-Host 'Stopped RustDesk Hub and deleted its named data volume.'
} else {
    & docker @compose down --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw 'Failed to stop RustDesk Hub.' }
    Write-Host 'Stopped RustDesk Hub; keys and database were preserved.'
}
