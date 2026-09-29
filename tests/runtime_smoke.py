import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = f"rustdesk-hub-smoke-{os.getpid()}"


def compose_prefix():
    return [
        shutil.which("docker") or "docker",
        "compose",
        "--project-name",
        PROJECT,
        "--project-directory",
        str(ROOT),
        "--env-file",
        str(ROOT / ".env.example"),
        "-f",
        str(ROOT / "compose.yaml"),
    ]


def run(args, env, check=True):
    return subprocess.run(args, env=env, check=check, text=True, capture_output=True)


def main() -> int:
    if not shutil.which("docker"):
        print("Docker CLI is unavailable", file=sys.stderr)
        return 2
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        print("Docker daemon is unavailable; runtime smoke test was not run", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.update(
        {
            "RUSTDESK_BIND_ADDRESS": "127.0.0.1",
            "RUSTDESK_PUBLIC_HOST": "127.0.0.1",
            # Let Docker choose ports so the smoke test works around OS/HNS
            # reserved-port ranges; the service targets remain 21115-21119.
            "RUSTDESK_NAT_TEST_PORT": "0",
            "RUSTDESK_RENDEZVOUS_PORT": "0",
            "RUSTDESK_RELAY_PORT": "0",
            "RUSTDESK_RELAY_ADVERTISED_PORT": "21117",
            "RUSTDESK_WS_RENDEZVOUS_PORT": "0",
            "RUSTDESK_WS_RELAY_PORT": "0",
            "RUSTDESK_HUB_IMAGE": "local/rustdesk-hub:smoke",
        }
    )
    prefix = compose_prefix()
    try:
        result = run(prefix + ["up", "--detach", "--build", "--wait", "--wait-timeout", "180"], env, check=False)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            return 1

        for service in ("hbbs", "hbbr"):
            container_id = run(prefix + ["ps", "--quiet", service], env).stdout.strip()
            inspect = run(["docker", "inspect", container_id], env).stdout
            state = json.loads(inspect)[0]["State"]
            if not state["Running"] or state["Health"]["Status"] != "healthy":
                raise AssertionError(f"{service} is not healthy: {state}")
            process_status = run(
                prefix
                + [
                    "exec",
                    "--no-TTY",
                    service,
                    "sh",
                    "-c",
                    "grep -E '^(Uid|Gid|CapEff):' /proc/1/status",
                ],
                env,
            ).stdout
            status_lines = dict(
                line.split(":", 1) for line in process_status.splitlines() if ":" in line
            )
            if set(status_lines["Uid"].split()) != {"10001"}:
                raise AssertionError(f"{service} did not drop to UID 10001: {process_status}")
            if set(status_lines["Gid"].split()) != {"10001"}:
                raise AssertionError(f"{service} did not drop to GID 10001: {process_status}")
            if int(status_lines["CapEff"].strip(), 16) != 0:
                raise AssertionError(f"{service} retained effective capabilities: {process_status}")

        mappings = {
            "nat": run(prefix + ["port", "hbbs", "21115", "--protocol", "tcp"], env).stdout.strip(),
            "rendezvous_tcp": run(prefix + ["port", "hbbs", "21116", "--protocol", "tcp"], env).stdout.strip(),
            "rendezvous_udp": run(prefix + ["port", "hbbs", "21116", "--protocol", "udp"], env).stdout.strip(),
            "relay": run(prefix + ["port", "hbbr", "21117", "--protocol", "tcp"], env).stdout.strip(),
            "rendezvous_ws": run(prefix + ["port", "hbbs", "21118", "--protocol", "tcp"], env).stdout.strip(),
            "relay_ws": run(prefix + ["port", "hbbr", "21119", "--protocol", "tcp"], env).stdout.strip(),
        }
        for name, mapping in mappings.items():
            if not mapping or ":" not in mapping:
                raise AssertionError(f"{name} mapping is missing: {mapping!r}")
            if name == "rendezvous_udp":
                continue
            host, port_text = mapping.rsplit(":", 1)
            with socket.create_connection((host, int(port_text)), timeout=3):
                pass

        udp_host, udp_port = mappings["rendezvous_udp"].rsplit(":", 1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.sendto(b"smoke", (udp_host, int(udp_port)))

        public_key = run(
            prefix + ["exec", "--no-TTY", "hbbs", "cat", "/data/id_ed25519.pub"],
            env,
        ).stdout.strip()
        if len(public_key) < 32:
            raise AssertionError("RustDesk public key was not generated")

        run(prefix + ["restart", "hbbs"], env)
        hbbs_id = run(prefix + ["ps", "--quiet", "hbbs"], env).stdout.strip()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state = json.loads(run(["docker", "inspect", hbbs_id], env).stdout)[0]["State"]
            if state["Running"] and state.get("Health", {}).get("Status") == "healthy":
                break
            time.sleep(1)
        else:
            raise AssertionError(f"hbbs was not healthy after restart: {state}")
        restarted_key = run(
            prefix + ["exec", "--no-TTY", "hbbs", "cat", "/data/id_ed25519.pub"],
            env,
        ).stdout.strip()
        if restarted_key != public_key:
            raise AssertionError("RustDesk public key changed after service restart")

        probe = run(prefix + ["--profile", "tools", "run", "--rm", "--no-deps", "client-probe"], env)
        if "internal client probe passed" not in probe.stdout:
            raise AssertionError(f"Container client probe did not pass: {probe.stdout}\n{probe.stderr}")

        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as output_dir:
            onboarding = run(
                [
                    sys.executable,
                    str(ROOT / "client" / "onboard.py"),
                    "--host",
                    "127.0.0.1",
                    "--key",
                    public_key,
                    "--platform",
                    "all",
                    "--output",
                    output_dir,
                    "--binary",
                    sys.executable,
                ],
                env,
            )
            if "Generated 3 profile(s)" not in onboarding.stdout:
                raise AssertionError(f"Client onboarding failed: {onboarding.stdout}\n{onboarding.stderr}")
            for target in ("windows", "linux", "macos"):
                profile = Path(output_dir) / target / "RustDesk2.toml"
                if not profile.is_file() or public_key not in profile.read_text(encoding="utf-8"):
                    raise AssertionError(f"Generated {target} profile is missing or has the wrong key")

        print(
            "Runtime smoke test passed: services healthy/non-root, ports reachable, "
            "UDP mapped, identity survived restart, and client onboarding/probe passed."
        )
        return 0
    finally:
        subprocess.run(prefix + ["down", "--volumes", "--remove-orphans"], env=env, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
