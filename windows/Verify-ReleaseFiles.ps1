[CmdletBinding()]
param([string] $BundleRoot = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = 'Stop'
$BundleRoot = (Resolve-Path -LiteralPath $BundleRoot).Path
$manifestPath = Join-Path $BundleRoot 'RELEASE-MANIFEST.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Release manifest was not found: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$expected = @($manifest.files | ForEach-Object { $_.path } | Sort-Object)
$actual = @(Get-ChildItem -LiteralPath $BundleRoot -File -Recurse |
    Where-Object { $_.FullName -ne $manifestPath } |
    ForEach-Object { $_.FullName.Substring($BundleRoot.Length + 1).Replace('\', '/') } |
    Sort-Object)
$difference = Compare-Object -ReferenceObject $expected -DifferenceObject $actual
if ($difference) { throw "Release files differ from the manifest: $($difference | Out-String)" }

foreach ($file in $manifest.files) {
    $path = Join-Path $BundleRoot ($file.path -replace '/', [IO.Path]::DirectorySeparatorChar)
    $item = Get-Item -LiteralPath $path
    if ($item.Length -ne [int64]$file.size) { throw "Size mismatch: $($file.path)" }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $file.sha256) { throw "SHA-256 mismatch: $($file.path)" }
}

Write-Host "Release file verification: PASS ($($actual.Count) files, version $($manifest.version))"
