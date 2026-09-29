import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IS_RELEASE_BUNDLE = (ROOT / "RELEASE-MANIFEST.json").is_file()


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class RustDeskHubBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose_text = read("compose.yaml")
        cls.config = None
        docker = shutil.which("docker")
        if not docker:
            return
        command = [
            docker,
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(ROOT / ".env.example"),
            "--profile",
            "tools",
            "-f",
            str(ROOT / "compose.yaml"),
            "config",
            "--format",
            "json",
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError(f"docker compose config failed:\n{result.stdout}\n{result.stderr}")
        cls.config = json.loads(result.stdout)

    def require_normalized_compose(self):
        if self.config is None:
            self.skipTest("Docker CLI is unavailable; raw Compose contract tests still run")

    def test_expected_artifacts_exist(self):
        expected = [
            "compose.yaml",
            "Dockerfile",
            "docker-entrypoint.sh",
            ".env.example",
            "README.md",
            "NOTICE.md",
            "client/RustDesk2.toml.example",
            "client/ONBOARDING.md",
            "client/onboard.py",
            "client/onboard.sh",
            "client/Onboard.ps1",
            "windows/Verify-ReleaseFiles.ps1",
            "scripts/start.sh",
            "scripts/stop.sh",
            "scripts/status.sh",
            "scripts/Start.ps1",
            "scripts/Stop.ps1",
            "scripts/Status.ps1",
            "scripts/probe-client.sh",
            "scripts/Probe-Client.ps1",
            "tests/runtime_smoke.py",
            "tests/test_onboarding.py",
        ]
        if not IS_RELEASE_BUNDLE:
            expected.append("packaging/README.md")
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())

    def test_services_and_official_pinned_upstream(self):
        self.require_normalized_compose()
        self.assertEqual(set(self.config["services"]), {"hbbs", "hbbr", "client-probe"})
        env_text = read(".env.example")
        self.assertIn(
            "RUSTDESK_SERVER_IMAGE=rustdesk/rustdesk-server:1.1.16@sha256:",
            env_text,
        )
        dockerfile = read("Dockerfile")
        self.assertIn("FROM ${RUSTDESK_UPSTREAM_IMAGE} AS rustdesk-upstream", dockerfile)
        self.assertIn("COPY --from=rustdesk-upstream /usr/bin/hbbs", dockerfile)
        self.assertIn("COPY --from=rustdesk-upstream /usr/bin/hbbr", dockerfile)

    def test_required_port_matrix_is_exact(self):
        self.require_normalized_compose()
        actual = set()
        for service_name, service in self.config["services"].items():
            for port in service.get("ports", []):
                actual.add(
                    (
                        service_name,
                        int(port["target"]),
                        int(port["published"]),
                        port["protocol"],
                        port["host_ip"],
                    )
                )
        expected = {
            ("hbbs", 21115, 21115, "tcp", "127.0.0.1"),
            ("hbbs", 21116, 21116, "tcp", "127.0.0.1"),
            ("hbbs", 21116, 21116, "udp", "127.0.0.1"),
            ("hbbs", 21118, 21118, "tcp", "127.0.0.1"),
            ("hbbr", 21117, 21117, "tcp", "127.0.0.1"),
            ("hbbr", 21119, 21119, "tcp", "127.0.0.1"),
        }
        self.assertEqual(actual, expected)

    def test_healthchecks_probe_real_listeners(self):
        self.require_normalized_compose()
        hbbs_probe = " ".join(self.config["services"]["hbbs"]["healthcheck"]["test"])
        hbbr_probe = " ".join(self.config["services"]["hbbr"]["healthcheck"]["test"])
        for token in ("127.0.0.1", "21116", "21118", "nc -z"):
            self.assertIn(token, hbbs_probe)
        for token in ("127.0.0.1", "21117", "21119", "nc -z"):
            self.assertIn(token, hbbr_probe)
        self.assertEqual(
            self.config["services"]["hbbr"]["depends_on"]["hbbs"]["condition"],
            "service_healthy",
        )

    def test_internal_client_probe_is_isolated_and_checks_both_services(self):
        self.require_normalized_compose()
        probe = self.config["services"]["client-probe"]
        command = " ".join(probe["command"])
        for token in ("hbbs 21116", "hbbs 21118", "hbbr 21117", "hbbr 21119"):
            self.assertIn(token, command)
        self.assertEqual(probe["profiles"], ["tools"])
        self.assertTrue(probe["read_only"])
        self.assertIn("ALL", probe["cap_drop"])
        self.assertFalse(probe.get("ports"))
        self.assertEqual(probe["depends_on"]["hbbs"]["condition"], "service_healthy")
        self.assertEqual(probe["depends_on"]["hbbr"]["condition"], "service_healthy")

    def test_encryption_key_and_persistent_storage_are_shared(self):
        self.require_normalized_compose()
        for service_name in ("hbbs", "hbbr"):
            service = self.config["services"][service_name]
            command = service["command"]
            self.assertIn("-k", command)
            self.assertEqual(command[command.index("-k") + 1], "_")
            mounts = service["volumes"]
            self.assertTrue(any(m["target"] == "/data" and m["type"] == "volume" for m in mounts))
        self.assertEqual(self.config["services"]["hbbs"]["environment"]["DB_URL"], "/data/db_v2.sqlite3")

    def test_container_hardening(self):
        self.require_normalized_compose()
        for service_name in ("hbbs", "hbbr"):
            service = self.config["services"][service_name]
            self.assertTrue(service["read_only"])
            self.assertIn("ALL", service["cap_drop"])
            self.assertIn("SETGID", service["cap_add"])
            self.assertIn("SETUID", service["cap_add"])
            self.assertIn("no-new-privileges:true", service["security_opt"])
            self.assertNotIn("privileged", service)
            self.assertNotEqual(service.get("network_mode"), "host")
            self.assertEqual(service["logging"]["options"]["max-size"], "10m")
        entrypoint = read("docker-entrypoint.sh")
        self.assertIn("su-exec rustdesk", entrypoint)
        self.assertIn("chmod 0600 /data/id_ed25519", entrypoint)

    def test_safe_defaults_and_scripts_enforce_health(self):
        env_text = read(".env.example")
        self.assertIn("RUSTDESK_BIND_ADDRESS=127.0.0.1", env_text)
        self.assertIn("RUSTDESK_ALWAYS_USE_RELAY=N", env_text)
        self.assertIn("Refusing public bind", read("scripts/common.sh"))
        self.assertIn("Refusing public bind", read("scripts/Common.ps1"))
        self.assertIn(".State.Health.Status", read("scripts/status.sh"))
        self.assertIn(".State.Health.Status", read("scripts/Status.ps1"))
        self.assertIn("--volumes", read("scripts/stop.sh"))
        self.assertIn("--volumes", read("scripts/Stop.ps1"))

    def test_generated_profiles_and_local_secrets_are_ignored(self):
        if IS_RELEASE_BUNDLE:
            self.skipTest("Source-control ignore rules are intentionally not shipped in the release ZIP")
        gitignore = read(".gitignore")
        for pattern in (".env", "client/generated/", "client/generated-*/", "__pycache__/", "*.pyc"):
            self.assertIn(pattern, gitignore)
        dockerignore = read(".dockerignore")
        self.assertIn(".env", dockerignore)
        self.assertIn("client", dockerignore)

    def test_raw_compose_contract_without_normalizer(self):
        text = self.compose_text
        for service in ("  hbbs:", "  hbbr:", "  client-probe:"):
            self.assertIn(service, text)
        for port in ("21115", "21116", "21117", "21118", "21119"):
            self.assertIn(f"target: {port}", text)
        self.assertIn("service_healthy", text)
        self.assertIn("nc -z -w 2 127.0.0.1 21116", text)
        self.assertIn("nc -z -w 2 127.0.0.1 21117", text)
        self.assertIn("read_only: true", text)
        self.assertIn("cap_drop:", text)
        self.assertIn("RUSTDESK_RELAY_ADVERTISED_PORT", text)

    def test_client_template_has_only_oss_fields(self):
        template = read("client/RustDesk2.toml.example")
        self.assertIn("custom-rendezvous-server", template)
        self.assertIn("relay-server", template)
        self.assertIn("key =", template)
        self.assertNotIn("api-server", template.lower())
        onboarding = read("client/onboard.py")
        self.assertIn('"--option", name, value', onboarding)
        self.assertIn('"--option", name', onboarding)
        self.assertIn("options-backup-", onboarding)


if __name__ == "__main__":
    unittest.main(verbosity=2)
