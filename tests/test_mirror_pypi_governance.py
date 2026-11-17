"""tools/mirror_pypi_governance.py: copies the governance artifacts byte-for-byte and records provenance."""
import datetime
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from sitecopy import SiteCopyTestCase

SOURCES = {
    "pypi-packages.v1.json": "governance/pypi/pypi-packages.v1.json",
    "canonical/publish-pypi.yml": "governance/pypi/canonical/publish-pypi.yml",
    "canonical/szl_pypi_release_gate.py": "governance/pypi/canonical/szl_pypi_release_gate.py",
    "canonical/gen_publish_workflow.py": "governance/pypi/canonical/gen_publish_workflow.py",
}
GIT = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
       "-c", "init.defaultBranch=main"]


@unittest.skipUnless(shutil.which("git"), "needs git to build a source-checkout fixture")
class MirrorPypiGovernanceTest(SiteCopyTestCase):
    def make_source_checkout(self):
        tmp = tempfile.TemporaryDirectory(prefix="szl-org-health-fixture-")
        self.addCleanup(tmp.cleanup)
        src = pathlib.Path(tmp.name)
        for i, rel in enumerate(SOURCES.values()):
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            # Bytes that a text-mode copy would mangle (CRLF, non-ASCII) prove the copy is byte-for-byte.
            (src / rel).write_bytes(f"fixture {i}\r\nnon-ascii: — é\n".encode("utf-8"))
        (src / "docs").mkdir()
        (src / "docs/PYPI_RELEASE_PATH.md").write_text("# Release path\n\nfixture contract\n", encoding="utf-8")
        for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
            subprocess.run(GIT + ["-C", str(src), *cmd], check=True, capture_output=True, timeout=60)
        sha = subprocess.run(GIT + ["-C", str(src), "rev-parse", "HEAD"], check=True, capture_output=True,
                             text=True, timeout=60).stdout.strip()
        return src, sha

    def test_mirrors_files_byte_for_byte_and_records_provenance(self):
        src, sha = self.make_source_checkout()
        before_meta = json.loads(self.read("pypi/MIRROR.json"))
        r = self.run_tool("mirror_pypi_governance.py", str(src))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"mirrored {len(SOURCES) + 1} files from {sha[:12]}", r.stdout)
        for dst, rel in SOURCES.items():
            # Validate against committed source blobs, not a translated checkout.
            blob = subprocess.check_output(
                GIT + ["-C", str(src), "show", f"{sha}:{rel}"]
            )
            self.assertEqual((self.site / "pypi" / dst).read_bytes(), blob, dst)
        release_path = self.read("pypi/release-path.md")
        header, body = release_path.split("\n\n", 1)
        self.assertTrue(header.startswith("<!-- Public mirror. Source of truth: szl-holdings/szl-org-health"))
        self.assertIn(f"commit {sha}", header)
        self.assertEqual(body, "# Release path\n\nfixture contract\n")
        meta = json.loads(self.read("pypi/MIRROR.json"))
        self.assertEqual(meta["source_commit"], sha)
        for dst, rel in SOURCES.items():
            blob = subprocess.check_output(
                GIT + ["-C", str(src), "show", f"{sha}:{rel}"]
            )
            self.assertEqual(meta["source_sha256"][dst], hashlib.sha256(blob).hexdigest())
        mirrored = datetime.datetime.strptime(meta["mirrored_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc)
        self.assertLess(abs(datetime.datetime.now(datetime.timezone.utc) - mirrored), datetime.timedelta(minutes=10))
        for key in ("schema", "source_repository", "source_visibility", "files", "note"):
            self.assertEqual(meta[key], before_meta[key], key)

    def test_dirty_checkout_content_cannot_enter_the_public_mirror(self):
        src, sha = self.make_source_checkout()
        # Local Windows EOL conversion or unfinished private edits are never
        # authoritative: only the committed Git object is suitable to mirror.
        changed = src / SOURCES["pypi-packages.v1.json"]
        changed.write_bytes(b"LOCAL-UNCOMMITTED-ONLY\r\n")
        (src / "docs/PYPI_RELEASE_PATH.md").write_text(
            "LOCAL-DRAFT-NOT-APPROVED\n", encoding="utf-8"
        )
        result = self.run_tool("mirror_pypi_governance.py", str(src))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = subprocess.check_output(
            GIT + ["-C", str(src), "show",
                   f"{sha}:{SOURCES['pypi-packages.v1.json']}"]
        )
        data = (self.site / "pypi/pypi-packages.v1.json").read_bytes()
        self.assertEqual(data, expected)
        self.assertNotIn(b"LOCAL-UNCOMMITTED-ONLY", data)
        self.assertEqual(
            self.read("pypi/release-path.md").split("\n\n", 1)[1],
            "# Release path\n\nfixture contract\n",
        )

    def test_usage_error_without_source_path(self):
        r = self.run_tool("mirror_pypi_governance.py")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Usage: python3 tools/mirror_pypi_governance.py /path/to/szl-org-health", r.stdout)


if __name__ == "__main__":
    unittest.main()
