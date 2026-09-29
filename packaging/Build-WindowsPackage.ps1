[CmdletBinding()]
param(
    [string] $Version,
    [string] $OutputDirectory,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
$productRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repositoryRoot = (Resolve-Path (Join-Path $productRoot '..\..')).Path
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (-not $Version) {
    $Version = (Get-Content -LiteralPath (Join-Path $productRoot 'VERSION') -Raw).Trim()
}
if ($Version -notmatch '^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$') {
    throw "Invalid release version: $Version"
}

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $productRoot 'dist'
} elseif (-not [IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory = Join-Path $productRoot $OutputDirectory
}
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
[IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null

$packageName = "rustdesk-hub-windows-$Version"
$zipPath = Join-Path $OutputDirectory "$packageName.zip"
$checksumPath = "$zipPath.sha256"
foreach ($target in @($zipPath, $checksumPath)) {
    if (Test-Path -LiteralPath $target) {
        if (-not $Force) { throw "Release artifact already exists: $target (use -Force to replace it)" }
        Remove-Item -LiteralPath $target -Force
    }
}

$stageRoot = Join-Path $OutputDirectory ('.stage-' + [Guid]::NewGuid().ToString('N'))
$packageRoot = Join-Path $stageRoot $packageName
[IO.Directory]::CreateDirectory($packageRoot) | Out-Null

try {
    $allowlistPath = Join-Path $PSScriptRoot 'windows-files.txt'
    $files = Get-Content -LiteralPath $allowlistPath |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and -not $_.StartsWith('#') }
    if (($files | Sort-Object -Unique).Count -ne $files.Count) {
        throw 'The Windows package allowlist contains duplicate paths.'
    }

    foreach ($relativePath in $files) {
        if ([IO.Path]::IsPathRooted($relativePath) -or $relativePath -match '(^|[\\/])\.\.([\\/]|$)') {
            throw "Unsafe allowlist path: $relativePath"
        }
        $source = Join-Path $productRoot ($relativePath -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "Allowlisted release file does not exist: $relativePath"
        }
        $destination = Join-Path $packageRoot ($relativePath -replace '/', [IO.Path]::DirectorySeparatorChar)
        [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
    }

    Copy-Item -LiteralPath (Join-Path $repositoryRoot 'LICENSE') -Destination (Join-Path $packageRoot 'LICENSE')

    $gitCommit = 'unavailable'
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $candidateCommit = (& git -C $repositoryRoot rev-parse HEAD 2>$null)
        if ($LASTEXITCODE -eq 0 -and $candidateCommit) { $gitCommit = $candidateCommit.Trim() }
    }

    $manifestFiles = @()
    Get-ChildItem -LiteralPath $packageRoot -File -Recurse | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring($packageRoot.Length + 1).Replace('\', '/')
        $manifestFiles += [ordered]@{
            path = $relative
            size = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $manifest = [ordered]@{
        schemaVersion = 1
        product = 'RustDesk Hub'
        version = $Version
        platform = 'windows'
        package = $packageName
        gitCommit = $gitCommit
        builtAtUtc = [DateTime]::UtcNow.ToString('o')
        includesRustDeskClientGui = $false
        runtimePrerequisites = @(
            'Windows with PowerShell 5.1 or later',
            'Docker Desktop or Docker Engine with Docker Compose v2',
            'Python 3.10 or later for onboarding and automated tests only',
            'Official RustDesk desktop client installed separately for remote desktop and file transfer'
        )
        files = $manifestFiles
    }
    $manifestJson = $manifest | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText((Join-Path $packageRoot 'RELEASE-MANIFEST.json'), $manifestJson + "`n", $utf8NoBom)

    Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
    $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText($checksumPath, "$zipHash  $([IO.Path]::GetFileName($zipPath))`n", $utf8NoBom)

    [pscustomobject]@{
        Version = $Version
        Package = $zipPath
        Checksum = $checksumPath
        Sha256 = $zipHash
        IncludesRustDeskClientGui = $false
    }
} finally {
    if (Test-Path -LiteralPath $stageRoot) {
        $resolvedStage = (Resolve-Path -LiteralPath $stageRoot).Path
        if (-not $resolvedStage.StartsWith($OutputDirectory, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean unexpected staging directory: $resolvedStage"
        }
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
