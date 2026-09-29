[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')

Initialize-RustDeskEnv
Assert-DockerCli
Assert-SafeExposure
$compose = Get-ComposePrefix
& docker @compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed.' }
Assert-DockerDaemon
& docker @compose up --detach --build --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { throw 'RustDesk Hub failed to become healthy.' }
& (Join-Path $PSScriptRoot 'Status.ps1')
