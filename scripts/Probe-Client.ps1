[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')

Initialize-RustDeskEnv
Assert-DockerCli
Assert-DockerDaemon
$compose = Get-ComposePrefix
& docker @compose --profile tools run --rm client-probe
if ($LASTEXITCODE -ne 0) { throw 'RustDesk Hub internal client probe failed.' }
