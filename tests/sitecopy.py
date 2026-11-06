"""Shared helpers: run the repository's tools against a throw-away copy of the published tree.

The tools locate the site from their own path (tools/ -> repository root), so copying the tree and running the
copied script exercises the real command line, exit codes included, without touching the working tree.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
JUNK = shutil.ignore_patterns(".git", "__pycache__", "*.py[cod]", "*.egg-info", ".venv", "venv", ".pytest_cache",
                              ".ruff_cache", "build", "dist", "tests")


class SiteCopyTestCase(unittest.TestCase):
    """Each test gets self.site: a fresh copy of the repository tree (without .git and tests/)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="szlholdings-site-")
        self.addCleanup(self._tmp.cleanup)
        self.site = pathlib.Path(self._tmp.name) / "site"
        shutil.copytree(REPO, self.site, ignore=JUNK)

    def run_tool(self, name, *args):
        """Run tools/<name> from the copy in isolated mode; returns the CompletedProcess."""
        return subprocess.run([sys.executable, "-I", str(self.site / "tools" / name), *args],
                              capture_output=True, text=True, timeout=120, check=False)

    def read(self, rel):
        return (self.site / rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        (self.site / rel).write_text(text, encoding="utf-8")

    def edit(self, rel, old, new, count=1):
        text = self.read(rel)
        self.assertIn(old, text, f"fixture drifted: {old!r} not found in {rel}")
        self.write(rel, text.replace(old, new, count))
