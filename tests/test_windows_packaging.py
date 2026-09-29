import json
import re
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
ALLOWLIST = ROOT / "packaging" / "windows-files.txt"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "rustdesk-hub-release.yml"


def allowlisted_files():
    return [
        line.strip()
        for line in ALLOWLIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class WindowsPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (ROOT / "RELEASE-MANIFEST.json").is_file():
            raise unittest.SkipTest("Packaging source/workflow tests run in the repository, not inside the release ZIP")

    def test_version_and_dependency_metadata(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
        metadata = json.loads((ROOT / "THIRD_PARTY.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["schemaVersion"], 1)
        names = {item["name"] for item in metadata["components"]}
        self.assertEqual(names, {"RustDesk Server OSS", "Alpine Linux"})
        self.assertTrue(any(item["name"] == "RustDesk desktop client" for item in metadata["notBundled"]))

    def test_allowlist_is_complete_safe_and_duplicate_free(self):
        files = allowlisted_files()
        self.assertEqual(len(files), len(set(files)))
        required = {
            "compose.yaml",
            "Dockerfile",
            "NOTICE.md",
            "THIRD_PARTY.json",
            "client/onboard.py",
            "windows/Start-RustDesk-Hub.cmd",
            "windows/Onboard-RustDesk-Client.cmd",
            "windows/Test-Prerequisites.ps1",
            "windows/Verify-ReleaseFiles.ps1",
        }
        self.assertTrue(required.issubset(files))
        forbidden_suffixes = {".exe", ".msi", ".dll", ".pem", ".key", ".pyc"}
        for relative in files:
            with self.subTest(relative=relative):
                path = PurePosixPath(relative)
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertTrue((ROOT / Path(*path.parts)).is_file())
                self.assertNotIn(path.suffix.lower(), forbidden_suffixes)
                self.assertNotIn("generated", path.parts)
                self.assertNotIn("__pycache__", path.parts)

    def test_launchers_target_packaged_scripts(self):
        mappings = {
            "windows/Start-RustDesk-Hub.cmd": "scripts\\Start.ps1",
            "windows/Status-RustDesk-Hub.cmd": "scripts\\Status.ps1",
            "windows/Stop-RustDesk-Hub.cmd": "scripts\\Stop.ps1",
            "windows/Onboard-RustDesk-Client.cmd": "client\\Onboard.ps1",
            "windows/Test-Prerequisites.cmd": "Test-Prerequisites.ps1",
            "windows/Verify-Release-Files.cmd": "Verify-ReleaseFiles.ps1",
        }
        for launcher, target in mappings.items():
            with self.subTest(launcher=launcher):
                text = (ROOT / launcher).read_text(encoding="utf-8")
                self.assertIn(target, text)
                self.assertIn("%~dp0", text)
                self.assertIn("exit /b %ERRORLEVEL%", text)
                self.assertNotIn("ExecutionPolicy Bypass", text)

    def test_build_and_verifier_enforce_allowlist_and_no_gui_claim(self):
        build = (ROOT / "packaging" / "Build-WindowsPackage.ps1").read_text(encoding="utf-8")
        verify = (ROOT / "packaging" / "Test-WindowsPackage.ps1").read_text(encoding="utf-8")
        self.assertIn("windows-files.txt", build)
        self.assertIn("includesRustDeskClientGui = $false", build)
        self.assertIn("RELEASE-MANIFEST.json", build)
        self.assertIn("Get-FileHash", build)
        self.assertRegex(verify, r"exe\|msi\|dll")
        self.assertIn("SHA-256 mismatch", verify)
        self.assertIn("Compare-Object", verify)

    def test_release_workflow_builds_but_does_not_publish(self):
        self.assertTrue(WORKFLOW.is_file())
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("Build-WindowsPackage.ps1", text)
        self.assertIn("Test-WindowsPackaging.ps1", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("gh release", text.lower())
        self.assertNotIn("softprops/action-gh-release", text)
        action_refs = re.findall(r"uses:\s+[^@\s]+@([^\s#]+)", text)
        self.assertTrue(action_refs)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
