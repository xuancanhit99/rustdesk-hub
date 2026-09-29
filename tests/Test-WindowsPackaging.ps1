[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$productRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$testRoot = Join-Path $productRoot ('dist\.package-test-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($testRoot) | Out-Null

try {
    $buildResult = & (Join-Path $productRoot 'packaging\Build-WindowsPackage.ps1') `
        -OutputDirectory $testRoot -Force
    $verifyResult = & (Join-Path $productRoot 'packaging\Test-WindowsPackage.ps1') `
        -Package $buildResult.Package -Checksum $buildResult.Checksum -RunBundleTests

    $tamperRoot = Join-Path $testRoot 'tampered'
    [IO.Directory]::CreateDirectory($tamperRoot) | Out-Null
    $tamperedZip = Join-Path $tamperRoot ([IO.Path]::GetFileName($buildResult.Package))
    $tamperedChecksum = "$tamperedZip.sha256"
    Copy-Item -LiteralPath $buildResult.Package -Destination $tamperedZip
    Copy-Item -LiteralPath $buildResult.Checksum -Destination $tamperedChecksum
    $bytes = [IO.File]::ReadAllBytes($tamperedZip)
    if ($bytes.Length -lt 32) { throw 'Built ZIP is unexpectedly small.' }
    $bytes[16] = $bytes[16] -bxor 0xff
    [IO.File]::WriteAllBytes($tamperedZip, $bytes)

    $tamperRejected = $false
    try {
        & (Join-Path $productRoot 'packaging\Test-WindowsPackage.ps1') `
            -Package $tamperedZip -Checksum $tamperedChecksum
    } catch {
        if ($_.Exception.Message -notmatch 'SHA-256') { throw }
        $tamperRejected = $true
    }
    if (-not $tamperRejected) { throw 'Tampered ZIP was not rejected.' }

    [pscustomobject]@{
        PackageName = [IO.Path]::GetFileName($buildResult.Package)
        Sha256 = $buildResult.Sha256
        FileCount = $verifyResult.FileCount
        TamperRejected = $tamperRejected
    }
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        $resolvedTestRoot = (Resolve-Path -LiteralPath $testRoot).Path
        $distRoot = [IO.Path]::GetFullPath((Join-Path $productRoot 'dist'))
        if (-not $resolvedTestRoot.StartsWith($distRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean unexpected packaging test path: $resolvedTestRoot"
        }
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
    }
}
