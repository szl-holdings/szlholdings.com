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
        manifest_path = src / "governance/pypi/pypi-packages.v1.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({"schema": "szl.pypi-packages.v1", "generated_at": "2026-11-16T12:00:00Z",
            "packages": [
                {"name": "szl-public", "repo": "szl-public", "status": "published", "pypi_version": "1.2.0",
                 "pypi_url": "https://pypi.org/project/szl-public/", "source": "https://github.com/szl-holdings/szl-public"},
                {"name": "private-lab", "repo": "private-lab", "status": "hold", "reason": "CONFIDENTIAL FIXTURE"},
                {"name": "unreleased", "repo": "unreleased", "status": "queued"}]}), encoding="utf-8")
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
        self.assertIn(f"mirrored {len(SOURCES) + 2} files from {sha[:12]}", r.stdout)
        projected = json.loads(self.read("pypi/pypi-packages.v1.json"))
        self.assertEqual(projected["counts"], {"published": 1, "queued": 0})
        self.assertEqual([p["name"] for p in projected["packages"]], ["szl-public"])
        self.assertNotIn("private-lab", self.read("pypi/pypi-packages.v1.json"))
        self.assertNotIn("unreleased", self.read("pypi/pypi-packages.v1.json"))
        self.assertEqual(projected["public_projection"]["source_commit"], sha)
        for dst, rel in SOURCES.items():
            # Source provenance is the immutable Git object, never a checkout
            # that may have been transformed by platform EOL policy.
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
        public_bytes = (self.site / "pypi/pypi-packages.v1.json").read_bytes()
        self.assertEqual(
            meta["public_projection_sha256"],
            hashlib.sha256(public_bytes).hexdigest(),
        )
        source_bytes = subprocess.check_output(
            GIT + ["-C", str(src), "show",
                   f"{sha}:governance/pypi/pypi-packages.v1.json"]
        )
        self.assertEqual(
            projected["public_projection"]["source_manifest_sha256"],
            hashlib.sha256(source_bytes).hexdigest(),
        )
        self.assertIn("published packages only", meta["note"])
        self.assertEqual(meta["public_manifest_projection"], "szl.public-pypi-projection/v1")
        mirrored = datetime.datetime.strptime(meta["mirrored_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc)
        self.assertLess(abs(datetime.datetime.now(datetime.timezone.utc) - mirrored), datetime.timedelta(minutes=10))
        for key in ("schema", "source_repository", "source_visibility", "files"):
            self.assertEqual(meta[key], before_meta[key], key)

    def test_public_git_blobs_match_attested_mirror_digests(self):
        repo = pathlib.Path(__file__).resolve().parents[1]
        meta = json.loads((repo / "pypi/MIRROR.json").read_text(encoding="utf-8"))
        for rel, expected in sorted(meta["source_sha256"].items()):
            # The staged Git index is the exact tree published by GitHub CI;
            # a transformed checkout cannot mask a different committed blob.
            data = subprocess.check_output(
                GIT + ["-C", str(repo), "show", f":pypi/{rel}"]
            )
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected, rel)
        public = subprocess.check_output(
            GIT + ["-C", str(repo), "show", ":pypi/pypi-packages.v1.json"]
        )
        self.assertEqual(
            hashlib.sha256(public).hexdigest(), meta["public_projection_sha256"]
        )

    def test_usage_error_without_source_path(self):
        r = self.run_tool("mirror_pypi_governance.py")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Usage: python3 tools/mirror_pypi_governance.py /path/to/szl-org-health", r.stdout)


if __name__ == "__main__":
    unittest.main()
