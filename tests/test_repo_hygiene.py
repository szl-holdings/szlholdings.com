"""Repository hygiene. GitHub Pages serves this repository's root as-is, so whatever is tracked is published."""
import pathlib
import shutil
import subprocess
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "build", "dist", "__pycache__"}


def python_sources():
    return sorted(p for p in REPO.rglob("*.py") if not SKIP_DIRS.intersection(p.relative_to(REPO).parts))


class RepoHygieneTest(unittest.TestCase):
    def test_every_python_source_compiles(self):
        # Compiled in memory: unlike compileall, this writes no __pycache__ into the published tree.
        sources = python_sources()
        self.assertIn(REPO / "tools" / "verify_site.py", sources)
        self.assertIn(REPO / "pypi" / "canonical" / "szl_pypi_release_gate.py", sources)
        for path in sources:
            with self.subTest(path=str(path.relative_to(REPO))):
                compile(path.read_bytes(), str(path), "exec", dont_inherit=True)

    @unittest.skipUnless(shutil.which("git") and (REPO / ".git").exists(), "needs a git checkout of the repository")
    def test_no_bytecode_or_build_output_is_tracked(self):
        tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z"], check=True, capture_output=True,
                                 timeout=60).stdout.decode("utf-8").split("\0")
        junk = [f for f in tracked if f and ("__pycache__/" in f or f.endswith((".pyc", ".pyo"))
                                             or ".egg-info/" in f or f.startswith((".venv/", "build/", "dist/")))]
        self.assertEqual(junk, [], "build by-products are tracked (and would be published by Pages)")


if __name__ == "__main__":
    unittest.main()
