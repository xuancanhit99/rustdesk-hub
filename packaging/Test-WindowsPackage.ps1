[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $Package,
    [string] $Checksum,
    [string] $WorkDirectory,
    [switch] $RunBundleTests
)

$ErrorActionPreference = 'Stop'
$productRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Package = (Resolve-Path -LiteralPath $Package).Path
if (-not $Checksum) { $Checksum = "$Package.sha256" }
$Checksum = (Resolve-Path -LiteralPath $Checksum).Path

if (-not $WorkDirectory) { $WorkDirectory = Join-Path $productRoot 'dist' }
if (-not [IO.Path]::IsPathRooted($WorkDirectory)) { $WorkDirectory = Join-Path $productRoot $WorkDirectory }
$WorkDirectory = [IO.Path]::GetFullPath($WorkDirectory)
[IO.Directory]::CreateDirectory($WorkDirectory) | Out-Null
$extractRoot = Join-Path $WorkDirectory ('.verify-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($extractRoot) | Out-Null

try {
    $checksumLine = (Get-Content -LiteralPath $Checksum -Raw).Trim()
    if ($checksumLine -notmatch '^([0-9a-fA-F]{64})\s{2}([^\\/]+\.zip)$') {
        throw 'Checksum file must contain: <64 hex chars><two spaces><zip filename>.'
    }
    if ($Matches[2] -ne [IO.Path]::GetFileName($Package)) { throw 'Checksum filename does not match the ZIP.' }
    $actualZipHash = (Get-FileHash -LiteralPath $Package -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualZipHash -ne $Matches[1].ToLowerInvariant()) { throw 'ZIP SHA-256 does not match its checksum file.' }

    Expand-Archive -LiteralPath $Package -DestinationPath $extractRoot
    $roots = @(Get-ChildItem -LiteralPath $extractRoot -Directory)
    if ($roots.Count -ne 1) { throw 'ZIP must contain exactly one top-level product directory.' }
    $bundleRoot = $roots[0].FullName
    $manifestPath = Join-Path $bundleRoot 'RELEASE-MANIFEST.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'RELEASE-MANIFEST.json is missing.' }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.includesRustDeskClientGui -ne $false) { throw 'Manifest must explicitly state that no GUI client is bundled.' }

    $manifestPaths = @($manifest.files | ForEach-Object { $_.path } | Sort-Object)
    $actualFiles = @(Get-ChildItem -LiteralPath $bundleRoot -File -Recurse |
        Where-Object { $_.FullName -ne $manifestPath } |
        ForEach-Object { $_.FullName.Substring($bundleRoot.Length + 1).Replace('\', '/') } |
        Sort-Object)
    $difference = Compare-Object -ReferenceObject $manifestPaths -DifferenceObject $actualFiles
    if ($difference) { throw "Manifest file list differs from ZIP contents: $($difference | Out-String)" }

    foreach ($file in $manifest.files) {
        $path = Join-Path $bundleRoot ($file.path -replace '/', [IO.Path]::DirectorySeparatorChar)
        $item = Get-Item -LiteralPath $path
        if ($item.Length -ne [int64]$file.size) { throw "Size mismatch: $($file.path)" }
        $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $file.sha256) { throw "SHA-256 mismatch: $($file.path)" }
    }

    $forbidden = @(
        '(?i)(^|/)\.env$',
        '(?i)(^|/)id_ed25519(?:\.priv)?$',
        '(?i)(^|/)(data|dist|generated[^/]*)/',
        '(?i)(^|/)__pycache__/',
        '(?i)\.(exe|msi|dll|dmg|deb|rpm|appimage|pem|key|pyc)$',
        '(?i)(^|/)\.git/'
    )
    foreach ($path in $actualFiles) {
        foreach ($pattern in $forbidden) {
            if ($path -match $pattern) { throw "Forbidden release payload: $path" }
        }
    }
    foreach ($required in @(
        'compose.yaml',
        'LICENSE',
        'NOTICE.md',
        'THIRD_PARTY.json',
        'windows/Start-RustDesk-Hub.cmd',
        'windows/Onboard-RustDesk-Client.cmd',
        'windows/Verify-ReleaseFiles.ps1',
        'client/onboard.py'
    )) {
        if ($actualFiles -notcontains $required) { throw "Required release file is missing: $required" }
    }

    & (Join-Path $bundleRoot 'windows\Verify-ReleaseFiles.ps1') -BundleRoot $bundleRoot

    if ($RunBundleTests) {
        Push-Location $bundleRoot
        try {
            & (Join-Path $bundleRoot 'tests\Run-Tests.ps1')
            if ($LASTEXITCODE -ne 0) { throw 'Tests from the extracted release bundle failed.' }
        } finally {
            Pop-Location
        }
    }

    [pscustomobject]@{
        Package = $Package
        Version = $manifest.version
        FileCount = $actualFiles.Count
        Sha256 = $actualZipHash
        BundleTestsRun = [bool]$RunBundleTests
    }
} finally {
    if (Test-Path -LiteralPath $extractRoot) {
        $resolvedExtract = (Resolve-Path -LiteralPath $extractRoot).Path
        if (-not $resolvedExtract.StartsWith($WorkDirectory, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean unexpected verification directory: $resolvedExtract"
        }
        Remove-Item -LiteralPath $resolvedExtract -Recurse -Force
    }
}
