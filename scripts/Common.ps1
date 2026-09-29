$script:RootDir = Split-Path -Parent $PSScriptRoot
$script:EnvFile = if ($env:RUSTDESK_ENV_FILE) { $env:RUSTDESK_ENV_FILE } else { Join-Path $script:RootDir '.env' }
$script:ComposeFile = Join-Path $script:RootDir 'compose.yaml'

function Initialize-RustDeskEnv {
    if (-not (Test-Path -LiteralPath $script:EnvFile)) {
        Copy-Item -LiteralPath (Join-Path $script:RootDir '.env.example') -Destination $script:EnvFile
        Write-Host "Created $script:EnvFile from .env.example"
    }
}

function Assert-DockerCli {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker CLI was not found.'
    }
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is not available.' }
}

function Assert-DockerDaemon {
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker daemon is not reachable. Start Docker and retry.' }
}

function Get-ComposePrefix {
    return @(
        'compose',
        '--project-directory', $script:RootDir,
        '--env-file', $script:EnvFile,
        '-f', $script:ComposeFile
    )
}

function Get-EnvValue([string] $Name, [string] $DefaultValue) {
    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if ($processValue) { return $processValue }
    $line = Get-Content -LiteralPath $script:EnvFile |
        Where-Object { $_ -match "^$([Regex]::Escape($Name))=" } |
        Select-Object -Last 1
    if ($line) { return ($line -split '=', 2)[1] }
    return $DefaultValue
}

function Assert-SafeExposure {
    $bindAddress = Get-EnvValue 'RUSTDESK_BIND_ADDRESS' '127.0.0.1'
    $publicHost = Get-EnvValue 'RUSTDESK_PUBLIC_HOST' '127.0.0.1'
    if ($bindAddress -notin @('127.0.0.1', '::1') -and
        $publicHost -in @('', '127.0.0.1', 'localhost', 'rustdesk.example.com')) {
        throw "Refusing public bind with placeholder RUSTDESK_PUBLIC_HOST=$publicHost. Update $script:EnvFile first."
    }
}
