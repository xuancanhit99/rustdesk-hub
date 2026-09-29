#!/usr/bin/env python3
"""Tạo, xác minh, áp dụng và khởi chạy hồ sơ ứng dụng khách RustDesk Hub."""

from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import os
import platform as platform_module
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PRODUCT_ROOT / "client" / "generated"
SUPPORTED_PLATFORMS = ("windows", "linux", "macos")
OPTION_NAMES = ("custom-rendezvous-server", "relay-server", "key")
APPLY_ORDER = ("key", "relay-server", "custom-rendezvous-server")


class OnboardingError(RuntimeError):
    pass


def current_platform() -> str:
    value = platform_module.system().lower()
    return {"darwin": "macos", "windows": "windows", "linux": "linux"}.get(value, value)


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def host_port(host: str, port: int) -> str:
    return f"[{host}]:{port}" if ":" in host and not host.startswith("[") else f"{host}:{port}"


def validate_host(host: str) -> str:
    host = host.strip()
    if not host or any(char.isspace() for char in host):
        raise OnboardingError("Server host must be non-empty and contain no whitespace.")
    if "://" in host or "/" in host:
        raise OnboardingError("Pass a DNS name or IP only, without a URL scheme or path.")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if ":" in host:
        try:
            if ipaddress.ip_address(host).version != 6:
                raise ValueError
        except ValueError as exc:
            raise OnboardingError(
                "A host containing ':' must be a bare IPv6 address; pass ports with --id-port/--relay-port."
            ) from exc
    return host


def validate_key(key: str) -> str:
    key = key.strip()
    try:
        decoded = base64.b64decode(key, validate=True)
    except Exception as exc:
        raise OnboardingError("RustDesk key must be valid base64.") from exc
    if len(decoded) != 32:
        raise OnboardingError(f"RustDesk public key must decode to 32 bytes, got {len(decoded)}.")
    return key


def key_fingerprint(key: str) -> str:
    digest = hashlib.sha256(base64.b64decode(key)).hexdigest()
    return ":".join(digest[index : index + 2] for index in range(0, 24, 2))


def query_running_server_key() -> str | None:
    docker = shutil.which("docker")
    if not docker:
        return None
    command = [
        docker,
        "compose",
        "--project-directory",
        str(PRODUCT_ROOT),
    ]
    env_file = Path(os.environ.get("RUSTDESK_ENV_FILE", PRODUCT_ROOT / ".env")).expanduser()
    if env_file.is_file():
        command.extend(["--env-file", str(env_file)])
    command.extend(
        [
            "-f",
            str(PRODUCT_ROOT / "compose.yaml"),
            "exec",
            "--no-TTY",
            "hbbs",
            "cat",
            "/data/id_ed25519.pub",
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def common_binary_candidates(target_platform: str) -> list[Path]:
    candidates: list[Path] = []
    located = shutil.which("rustdesk.exe" if target_platform == "windows" else "rustdesk")
    if located:
        candidates.append(Path(located))
    if target_platform == "windows":
        for env_name, suffixes in (
            ("ProgramFiles", (("RustDesk", "rustdesk.exe"),)),
            ("ProgramFiles(x86)", (("RustDesk", "rustdesk.exe"),)),
            (
                "LOCALAPPDATA",
                (
                    ("Programs", "RustDesk", "rustdesk.exe"),
                    ("rustdesk", "rustdesk.exe"),
                ),
            ),
        ):
            base = os.environ.get(env_name)
            if base:
                candidates.extend(Path(base).joinpath(*suffix) for suffix in suffixes)
    elif target_platform == "linux":
        candidates.extend(Path(path) for path in ("/usr/bin/rustdesk", "/usr/local/bin/rustdesk", "/opt/rustdesk/rustdesk"))
    elif target_platform == "macos":
        candidates.extend(
            (
                Path("/Applications/RustDesk.app/Contents/MacOS/RustDesk"),
                Path.home() / "Applications/RustDesk.app/Contents/MacOS/RustDesk",
            )
        )
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def detect_binary(target_platform: str, explicit: str | None = None) -> tuple[Path | None, str | None]:
    if explicit:
        located = shutil.which(explicit)
        candidates = [Path(located) if located else Path(explicit).expanduser()]
    else:
        candidates = common_binary_candidates(target_platform)
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            result = subprocess.run(
                [str(candidate), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        version = (result.stdout or result.stderr).strip().splitlines()
        if result.returncode == 0 and version:
            return candidate.resolve(), version[0]
    return None, None


def looks_like_rustdesk_version(version: str | None) -> bool:
    if not version:
        return False
    value = version.strip().lower()
    if value.startswith("rustdesk"):
        value = value.removeprefix("rustdesk").strip(" v")
    parts = value.split(".")
    return len(parts) >= 2 and all(part.isdigit() for part in parts[:2])


def target_config_path(target_platform: str) -> str:
    if target_platform == "windows":
        return r"%APPDATA%\RustDesk\config\RustDesk2.toml"
    if target_platform == "linux":
        return "${XDG_CONFIG_HOME:-$HOME/.config}/rustdesk/RustDesk2.toml"
    if target_platform == "macos":
        return "$HOME/Library/Preferences/com.carriez.RustDesk/RustDesk2.toml"
    raise OnboardingError(f"Unsupported platform: {target_platform}")


def render_toml(options: dict[str, str]) -> str:
    lines = [
        "# Được tạo bởi RustDesk Hub client/onboard.py.",
        "# Chỉ dành cho hồ sơ mới; không ghi đè tệp đang tồn tại.",
        "# Dùng --apply --yes để hợp nhất qua CLI chính thức của RustDesk.",
        "",
        "[options]",
    ]
    lines.extend(f"{name} = {json.dumps(options[name])}" for name in OPTION_NAMES)
    return "\n".join(lines) + "\n"


def generate_profiles(
    platforms: tuple[str, ...], output: Path, options: dict[str, str], fingerprint: str
) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for target_platform in platforms:
        directory = output / target_platform
        directory.mkdir(parents=True, exist_ok=True)
        config_path = directory / "RustDesk2.toml"
        config_path.write_text(render_toml(options), encoding="utf-8", newline="\n")
        manifest = {
            "platform": target_platform,
            "target_path": target_config_path(target_platform),
            "id_server": options["custom-rendezvous-server"],
            "relay_server": options["relay-server"],
            "key_sha256_prefix": fingerprint,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "apply_recommendation": "Use onboard.py --apply --yes; never overwrite an existing RustDesk2.toml.",
        }
        (directory / "profile.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        (directory / "README.txt").write_text(
            "Hồ sơ ứng dụng khách RustDesk Hub\n"
            f"Nền tảng đích: {target_platform}\n"
            f"Đường dẫn hồ sơ mới thường dùng: {manifest['target_path']}\n"
            "Cách cài ưu tiên: chạy onboard.py --apply --yes khi RustDesk đã được cài.\n"
            "Cách dự phòng: mở RustDesk > Settings > Network và nhập ba giá trị.\n"
            "Không ghi đè RustDesk2.toml đang tồn tại vì sẽ mất các cài đặt khác.\n",
            encoding="utf-8",
            newline="\n",
        )
        generated.append(config_path)
        if os.name != "nt":
            for generated_file in (config_path, directory / "profile.json", directory / "README.txt"):
                generated_file.chmod(0o600)
    return generated


def probe_endpoint(label: str, host: str, port: int, timeout: float) -> None:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        raise OnboardingError(f"{label} probe failed for {host_port(host, port)}: {exc}") from exc
    print(f"{label} probe: PASS ({host_port(host, port)})")


def apply_options(binary: Path, options: dict[str, str], output: Path, confirmed: bool) -> None:
    if not confirmed:
        raise OnboardingError("Applying client settings requires --yes because it changes the installed client.")
    backup: dict[str, str] = {}
    for name in OPTION_NAMES:
        result = subprocess.run(
            [str(binary), "--option", name], capture_output=True, text=True, timeout=15, check=False
        )
        if result.returncode != 0:
            combined = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
            raise OnboardingError(f"Could not read existing RustDesk option {name!r}: {combined or result.returncode}")
        backup[name] = result.stdout.strip()
    output.mkdir(parents=True, exist_ok=True)
    backup_path = output / f"options-backup-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json"
    backup_path.write_text(json.dumps(backup, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        backup_path.chmod(0o600)

    try:
        # Change the trust key first and the rendezvous endpoint last so a live
        # client never registers with the new server while still using the old key.
        for name in APPLY_ORDER:
            value = options[name]
            result = subprocess.run(
                [str(binary), "--option", name, value],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            combined = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
            if result.returncode != 0 or "required" in combined.lower() or "disabled" in combined.lower():
                raise OnboardingError(f"RustDesk rejected option {name!r}: {combined or result.returncode}")

        for name, expected in options.items():
            result = subprocess.run(
                [str(binary), "--option", name], capture_output=True, text=True, timeout=15, check=False
            )
            if result.returncode != 0 or result.stdout.strip() != expected:
                raise OnboardingError(
                    f"Could not verify option {name!r}. Run this command elevated on an installed RustDesk client."
                )
    except Exception:
        # A partial apply should not leave an installed client half-configured.
        for name in reversed(APPLY_ORDER):
            old_value = backup[name]
            subprocess.run(
                [str(binary), "--option", name, old_value],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        raise
    print(f"Applied and verified three RustDesk options. Previous values: {backup_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="RustDesk Hub DNS name or IP (without scheme/port)")
    parser.add_argument("--key", help="RustDesk Hub public key; auto-read from a running local hub when omitted")
    parser.add_argument("--id-port", type=int, default=21116)
    parser.add_argument("--relay-port", type=int, default=21117)
    parser.add_argument("--platform", choices=("auto", "all", *SUPPORTED_PLATFORMS), default="auto")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--binary", help="Explicit RustDesk executable to inspect/apply/launch")
    parser.add_argument("--check-only", action="store_true", help="Only detect and version-check the local client")
    parser.add_argument("--probe", action="store_true", help="Probe ID and relay TCP endpoints")
    parser.add_argument("--apply", action="store_true", help="Merge settings via RustDesk --option")
    parser.add_argument("--launch", action="store_true", help="Launch RustDesk after successful onboarding")
    parser.add_argument("--yes", action="store_true", help="Confirm the mutating --apply action")
    parser.add_argument("--timeout", type=float, default=5.0, help="Endpoint probe timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    local_platform = current_platform()
    binary, version = detect_binary(local_platform, args.binary)
    print(
        f"RustDesk client: {'found ' + str(binary) + ' (version ' + version + ')' if binary else 'not found'}"
    )
    if args.check_only:
        return 0 if binary else 4

    dotenv = load_dotenv(PRODUCT_ROOT / ".env") or load_dotenv(PRODUCT_ROOT / ".env.example")
    host = validate_host(args.host or dotenv.get("RUSTDESK_PUBLIC_HOST", ""))
    key = args.key or query_running_server_key()
    if not key:
        raise OnboardingError("No public key supplied and no running local hbbs key could be read.")
    key = validate_key(key)
    if not 1 <= args.id_port <= 65535 or not 1 <= args.relay_port <= 65535:
        raise OnboardingError("Ports must be between 1 and 65535.")

    options = {
        "custom-rendezvous-server": host_port(host, args.id_port),
        "relay-server": host_port(host, args.relay_port),
        "key": key,
    }
    targets = SUPPORTED_PLATFORMS if args.platform == "all" else (
        local_platform if args.platform == "auto" else args.platform,
    )
    if any(target not in SUPPORTED_PLATFORMS for target in targets):
        raise OnboardingError(f"Unsupported local platform: {local_platform}")
    fingerprint = key_fingerprint(key)
    generated = generate_profiles(targets, args.output.resolve(), options, fingerprint)
    print(f"Generated {len(generated)} profile(s) under {args.output.resolve()}")
    print(f"Server key SHA-256 prefix: {fingerprint}")
    if host in {"127.0.0.1", "::1", "localhost"}:
        print("WARNING: loopback profiles only work when client and hub run on the same machine.")

    if args.probe:
        probe_endpoint("ID server", host, args.id_port, args.timeout)
        probe_endpoint("Relay server", host, args.relay_port, args.timeout)
    if args.apply:
        if not binary:
            raise OnboardingError("RustDesk is not installed or its executable was not found; cannot --apply.")
        if not looks_like_rustdesk_version(version):
            raise OnboardingError(
                f"The selected executable did not report a RustDesk-like version ({version!r}); refusing --apply."
            )
        apply_options(binary, options, args.output.resolve(), args.yes)
    if args.launch:
        if not binary:
            raise OnboardingError("RustDesk executable was not found; cannot --launch.")
        if not looks_like_rustdesk_version(version):
            raise OnboardingError(
                f"The selected executable did not report a RustDesk-like version ({version!r}); refusing --launch."
            )
        subprocess.Popen([str(binary)], start_new_session=True)
        print(f"Launched {binary}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OnboardingError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
