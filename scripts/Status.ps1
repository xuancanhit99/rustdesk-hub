[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')

Initialize-RustDeskEnv
Assert-DockerCli
$compose = Get-ComposePrefix
& docker @compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed.' }
Assert-DockerDaemon
& docker @compose ps

$failed = $false
foreach ($service in @('hbbs', 'hbbr')) {
    $containerId = (& docker @compose ps --quiet $service).Trim()
    if (-not $containerId) {
        Write-Error "$service`: not created" -ErrorAction Continue
        $failed = $true
        continue
    }
    $running = (& docker inspect --format '{{.State.Running}}' $containerId).Trim()
    $health = (& docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' $containerId).Trim()
    Write-Host "$service`: running=$running health=$health"
    if ($running -ne 'true' -or $health -ne 'healthy') { $failed = $true }
}

if (-not $failed) {
    $publicKey = (& docker @compose exec --no-TTY hbbs sh -c 'cat /data/id_ed25519.pub 2>/dev/null || true').Trim()
    if ($publicKey) {
        Write-Host "RustDesk client public key: $publicKey"
    } else {
        Write-Error 'RustDesk client public key is not available yet.' -ErrorAction Continue
        $failed = $true
    }
} else {
    Write-Error 'RustDesk client public key check skipped because a service is unhealthy.' -ErrorAction Continue
}

if ($failed) { exit 1 }
