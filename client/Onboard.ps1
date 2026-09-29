[CmdletBinding()]
param(
    [string] $ServerHost,
    [string] $Key,
    [ValidateSet('auto', 'all', 'windows', 'linux', 'macos')]
    [string] $Platform = 'auto',
    [string] $Output,
    [string] $Binary,
    [int] $IdPort = 21116,
    [int] $RelayPort = 21117,
    [switch] $CheckOnly,
    [switch] $Probe,
    [switch] $Apply,
    [switch] $Launch,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required for client onboarding.' }

$arguments = @((Join-Path $PSScriptRoot 'onboard.py'), '--platform', $Platform, '--id-port', $IdPort, '--relay-port', $RelayPort)
if ($ServerHost) { $arguments += @('--host', $ServerHost) }
if ($Key) { $arguments += @('--key', $Key) }
if ($Output) { $arguments += @('--output', $Output) }
if ($Binary) { $arguments += @('--binary', $Binary) }
if ($CheckOnly) { $arguments += '--check-only' }
if ($Probe) { $arguments += '--probe' }
if ($Apply) { $arguments += '--apply' }
if ($Launch) { $arguments += '--launch' }
if ($Force) { $arguments += '--yes' }

if ($python.Name -eq 'py.exe') { $arguments = @('-3') + $arguments }
& $python.Source @arguments
exit $LASTEXITCODE
