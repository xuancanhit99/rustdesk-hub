# RustDesk Hub for Windows

This ZIP contains the RustDesk Hub server bundle, operational launchers and the
client onboarding CLI. It does **not** contain a RustDesk GUI executable.

## First run

1. Install and start Docker Desktop using Linux containers/WSL2.
2. Optionally install Python 3.10+ for onboarding and automated tests.
3. Run `windows\Test-Prerequisites.cmd`.
4. Copy `.env.example` to `.env` and review it.
5. Run `windows\Start-RustDesk-Hub.cmd`.
6. Run `windows\Status-RustDesk-Hub.cmd` and retain the public key.

The safe default listens only on `127.0.0.1`. Configure a real public host,
firewall and `RUSTDESK_BIND_ADDRESS=0.0.0.0` before onboarding remote machines.

For client setup, install a signed RustDesk release from
https://github.com/rustdesk/rustdesk/releases, then run:

```bat
windows\Onboard-RustDesk-Client.cmd -ServerHost rustdesk.example.com -Probe
```

Applying settings requires an elevated terminal and explicit confirmation:

```bat
windows\Onboard-RustDesk-Client.cmd -ServerHost rustdesk.example.com -Apply -Force
```

Verify the downloaded ZIP before extracting it:

```powershell
Get-FileHash .\rustdesk-hub-windows-0.1.0.zip -Algorithm SHA256
Get-Content .\rustdesk-hub-windows-0.1.0.zip.sha256
```

After the checksum matches, if Windows marks extracted scripts as downloaded
and your execution policy blocks them, explicitly unblock this verified bundle:

```powershell
Get-ChildItem .\rustdesk-hub-windows-0.1.0 -Recurse -File | Unblock-File
```

Then verify every extracted payload file against the signed-by-checksum
manifest:

```bat
windows\Verify-Release-Files.cmd
```

The release is an unsigned ZIP, not an installer. See `RELEASE-MANIFEST.json`,
`THIRD_PARTY.json` and `NOTICE.md` for exact contents and provenance.
