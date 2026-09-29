# Windows release packaging

The supported Windows artifact is an unsigned ZIP containing the Docker
Compose server bundle, operational PowerShell/CMD wrappers, client onboarding
CLI, documentation and tests. It deliberately contains no RustDesk GUI binary.

Build and verify locally:

```powershell
.\packaging\Build-WindowsPackage.ps1 -Force
.\packaging\Test-WindowsPackage.ps1 `
  -Package .\dist\rustdesk-hub-windows-0.1.0.zip `
  -RunBundleTests
```

Or run the complete packaging regression, including a tamper rejection check:

```powershell
.\tests\Test-WindowsPackaging.ps1
```

`windows-files.txt` is the only payload allowlist. The builder adds the
repository MIT `LICENSE`, then generates `RELEASE-MANIFEST.json` with every
file's size and SHA-256. The verifier rejects extra/missing files, executable
or installer payloads, private-key-like files, generated state and checksum
mismatches.

The ZIP also contains `windows/Verify-Release-Files.cmd`, which rechecks every
extracted payload against `RELEASE-MANIFEST.json`. The external `.zip.sha256`
must be checked first because the ZIP checksum is what protects the manifest.

The GitHub Actions workflow only uploads a workflow artifact. It has read-only
repository permissions and does not create a GitHub Release or publish images.

## Current blockers for an installer

- No Authenticode code-signing certificate or protected signing service is
  configured. Shipping an unsigned MSI/EXE would add SmartScreen friction and
  weaken provenance compared with the checksum-verifiable ZIP.
- No WiX Toolset/Inno Setup project, upgrade code, install scope or uninstall
  policy has been selected and reviewed.
- No RustDesk GUI binary is built by this repository. Bundling an upstream GUI
  would require an explicit version/signature verification and redistribution
  license review; the ZIP instead links to official signed client releases.
- The workflow has not been executed on GitHub yet, so hosted-runner behavior
  remains locally validated but remotely unproven until a push or dispatch.
