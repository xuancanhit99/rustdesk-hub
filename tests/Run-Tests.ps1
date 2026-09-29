[CmdletBinding()]
param([switch] $Runtime)

$ErrorActionPreference = 'Stop'
$rootDir = Split-Path -Parent $PSScriptRoot
python -m unittest discover -s (Join-Path $rootDir 'tests') -p 'test_*.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Static/Compose tests failed.' }

if ($Runtime) {
    python (Join-Path $rootDir 'tests/runtime_smoke.py')
    if ($LASTEXITCODE -ne 0) { throw 'Runtime smoke test failed.' }
}
