import base64
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "client" / "onboard.py"
SPEC = importlib.util.spec_from_file_location("rustdesk_hub_onboard", SCRIPT)
ONBOARD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(ONBOARD)
TEST_KEY = base64.b64encode(bytes(range(32))).decode("ascii")


class ClientOnboardingTests(unittest.TestCase):
    def test_rendered_profile_has_only_three_oss_network_options(self):
        options = {
            "custom-rendezvous-server": "rd.example:21116",
            "relay-server": "rd.example:21117",
            "key": TEST_KEY,
        }
        rendered = ONBOARD.render_toml(options)
        self.assertIn("[options]", rendered)
        for name, value in options.items():
            self.assertIn(f'{name} = "{value}"', rendered)
        self.assertNotIn("api-server", rendered.lower())

    def test_generate_all_platform_profiles_and_manifests(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--host",
                    "rd.example",
                    "--key",
                    TEST_KEY,
                    "--platform",
                    "all",
                    "--output",
                    temp_dir,
                    "--binary",
                    sys.executable,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for target in ONBOARD.SUPPORTED_PLATFORMS:
                with self.subTest(target=target):
                    profile_dir = Path(temp_dir) / target
                    self.assertTrue((profile_dir / "RustDesk2.toml").is_file())
                    manifest = json.loads((profile_dir / "profile.json").read_text(encoding="utf-8"))
                    self.assertEqual(manifest["platform"], target)
                    self.assertEqual(manifest["id_server"], "rd.example:21116")
                    self.assertEqual(manifest["relay_server"], "rd.example:21117")
                    self.assertNotIn(TEST_KEY, json.dumps(manifest))

    def test_ipv6_endpoints_are_bracketed(self):
        self.assertEqual(ONBOARD.host_port("2001:db8::5", 21116), "[2001:db8::5]:21116")
        self.assertEqual(ONBOARD.validate_host("[2001:db8::5]"), "2001:db8::5")

    def test_invalid_key_and_url_host_are_rejected(self):
        with self.assertRaises(ONBOARD.OnboardingError):
            ONBOARD.validate_key("not-base64")
        with self.assertRaises(ONBOARD.OnboardingError):
            ONBOARD.validate_key(base64.b64encode(b"too-short").decode("ascii"))
        with self.assertRaises(ONBOARD.OnboardingError):
            ONBOARD.validate_host("https://rd.example")
        with self.assertRaises(ONBOARD.OnboardingError):
            ONBOARD.validate_host("rd.example:21116")

    def test_explicit_executable_is_version_checked(self):
        binary, version = ONBOARD.detect_binary(ONBOARD.current_platform(), sys.executable)
        self.assertEqual(binary, Path(sys.executable).resolve())
        self.assertTrue(version)
        self.assertFalse(ONBOARD.looks_like_rustdesk_version(version))
        self.assertTrue(ONBOARD.looks_like_rustdesk_version("1.4.5"))
        self.assertTrue(ONBOARD.looks_like_rustdesk_version("RustDesk 1.4.5"))

    def test_query_command_uses_custom_env_file_when_present(self):
        original = ONBOARD.subprocess.run
        original_which = ONBOARD.shutil.which
        captured = {}

        class Result:
            returncode = 1
            stdout = ""

        def fake_run(command, **kwargs):
            captured["command"] = command
            return Result()

        ONBOARD.subprocess.run = fake_run
        ONBOARD.shutil.which = lambda name: "docker" if name == "docker" else original_which(name)
        try:
            import os

            with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp_dir:
                env_file = Path(temp_dir) / "hub.env"
                env_file.write_text("RUSTDESK_PUBLIC_HOST=rd.example\n", encoding="utf-8")
                prior = os.environ.get("RUSTDESK_ENV_FILE")
                os.environ["RUSTDESK_ENV_FILE"] = str(env_file)
                try:
                    ONBOARD.query_running_server_key()
                finally:
                    if prior is None:
                        os.environ.pop("RUSTDESK_ENV_FILE", None)
                    else:
                        os.environ["RUSTDESK_ENV_FILE"] = prior
            self.assertIn("--env-file", captured["command"])
            self.assertIn(str(env_file), captured["command"])
        finally:
            ONBOARD.subprocess.run = original
            ONBOARD.shutil.which = original_which

    def test_apply_requires_confirmation_before_mutation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp_dir:
            with self.assertRaises(ONBOARD.OnboardingError):
                ONBOARD.apply_options(
                    Path(sys.executable),
                    {
                        "custom-rendezvous-server": "rd.example:21116",
                        "relay-server": "rd.example:21117",
                        "key": TEST_KEY,
                    },
                    Path(temp_dir),
                    False,
                )

    def test_apply_rolls_back_already_changed_options_on_failure(self):
        original = ONBOARD.subprocess.run
        calls = []
        read_values = {
            "custom-rendezvous-server": "old-id:21116",
            "relay-server": "old-relay:21117",
            "key": "old-key",
        }

        class Result:
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def fake_run(command, **kwargs):
            calls.append(command)
            if len(command) >= 3 and command[1] == "--option":
                name = command[2]
                if len(command) == 3:
                    return Result(stdout=read_values[name] + "\n")
                if name == "relay-server" and command[3] == "rd.example:21117":
                    return Result(returncode=1, stderr="simulated failure")
                return Result()
            return Result()

        ONBOARD.subprocess.run = fake_run
        try:
            with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp_dir:
                with self.assertRaises(ONBOARD.OnboardingError):
                    ONBOARD.apply_options(
                        Path("rustdesk"),
                        {
                            "custom-rendezvous-server": "rd.example:21116",
                            "relay-server": "rd.example:21117",
                            "key": TEST_KEY,
                        },
                        Path(temp_dir),
                        True,
                    )
            self.assertIn(
                ["rustdesk", "--option", "custom-rendezvous-server", "old-id:21116"], calls
            )
        finally:
            ONBOARD.subprocess.run = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
