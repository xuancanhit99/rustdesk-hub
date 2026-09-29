[CmdletBinding()]
param([switch] $SkipDockerDaemon)

$ErrorActionPreference = 'Stop'
$failures = [Collections.Generic.List[string]]::new()
$warnings = [Collections.Generic.List[string]]::new()

function Invoke-NativeWithTimeout {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [string[]] $Arguments = @(),
        [int] $TimeoutSeconds = 10
    )
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = (($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + $_.Replace('"', '\"') + '"' } else { $_ }
    }) -join ' ')
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) { return [pscustomobject]@{ ExitCode = 1; TimedOut = $false; Output = '' } }
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch { }
            return [pscustomobject]@{ ExitCode = 124; TimedOut = $true; Output = '' }
        }
        $output = ($process.StandardOutput.ReadToEnd() + $process.StandardError.ReadToEnd()).Trim()
        return [pscustomobject]@{ ExitCode = $process.ExitCode; TimedOut = $false; Output = $output }
    } finally {
        $process.Dispose()
    }
}

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    $failures.Add('This release artifact targets Windows.')
}
if ($PSVersionTable.PSVersion -lt [Version]'5.1') {
    $failures.Add("PowerShell 5.1 or later is required; found $($PSVersionTable.PSVersion).")
}

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    $failures.Add('Docker CLI was not found. Install Docker Desktop or Docker Engine with Compose v2.')
} else {
    $composeVersion = Invoke-NativeWithTimeout -FilePath $docker.Path -Arguments @('compose', 'version') -TimeoutSeconds 30
    if ($composeVersion.TimedOut -or $composeVersion.ExitCode -ne 0) { $failures.Add('Docker Compose v2 is not available.') }
    if (-not $SkipDockerDaemon) {
        $dockerInfo = Invoke-NativeWithTimeout -FilePath $docker.Path -Arguments @('info') -TimeoutSeconds 30
        if ($dockerInfo.TimedOut -or $dockerInfo.ExitCode -ne 0) { $failures.Add('Docker daemon is not reachable; start Docker Desktop.') }
    }
}

$pythonCommand = Get-Command py -ErrorAction SilentlyContinue
$pythonArgs = @('-3')
if (-not $pythonCommand) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $pythonArgs = @()
}
if (-not $pythonCommand) {
    $warnings.Add('Python 3.10+ was not found. Server launch works, but onboarding/tests require Python.')
} else {
    $pythonResult = Invoke-NativeWithTimeout -FilePath $pythonCommand.Path -Arguments ($pythonArgs + @('--version'))
    $versionOutput = $pythonResult.Output
    if ($versionOutput -notmatch 'Python\s+(\d+)\.(\d+)') {
        $warnings.Add("Could not determine Python version: $versionOutput")
    } elseif ([Version]"$($Matches[1]).$($Matches[2])" -lt [Version]'3.10') {
        $warnings.Add("Python 3.10+ is required for onboarding/tests; found $versionOutput.")
    }
}

$rustDeskCandidates = @(
    (Get-Command rustdesk.exe -ErrorAction SilentlyContinue).Source,
    (Join-Path $env:ProgramFiles 'RustDesk\rustdesk.exe'),
    $(if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} 'RustDesk\rustdesk.exe' }),
    $(if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Programs\RustDesk\rustdesk.exe' })
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
if (-not $rustDeskCandidates) {
    $warnings.Add('RustDesk GUI is not bundled or installed. Download an official signed client for remote sessions.')
}

foreach ($warning in $warnings) { Write-Warning $warning }
if ($failures.Count) {
    foreach ($failure in $failures) { Write-Error $failure -ErrorAction Continue }
    exit 1
}
Write-Host 'RustDesk Hub Windows prerequisites: PASS'
exit 0
