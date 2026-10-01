#!/usr/bin/env python3
"""Refresh pypi/ from a local checkout of szl-holdings/szl-org-health. Standard library only.

Usage: python3 tools/mirror_pypi_governance.py /path/to/szl-org-health
Copies the manifest, the release contract, and the canonical workflow/gate/generator byte-for-byte, prefixes
release-path.md with a provenance comment, and rewrites MIRROR.json with the source commit and time.
"""
import datetime, json, pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = {
    "pypi-packages.v1.json": "governance/pypi/pypi-packages.v1.json",
    "canonical/publish-pypi.yml": "governance/pypi/canonical/publish-pypi.yml",
    "canonical/szl_pypi_release_gate.py": "governance/pypi/canonical/szl_pypi_release_gate.py",
    "canonical/gen_publish_workflow.py": "governance/pypi/canonical/gen_publish_workflow.py",
}

def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__); return 2
    src = pathlib.Path(sys.argv[1]).resolve()
    sha = subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"], text=True).strip()
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for dst, rel in FILES.items():
        (ROOT / "pypi" / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, ROOT / "pypi" / dst)
    doc = (src / "docs/PYPI_RELEASE_PATH.md").read_text(encoding="utf-8")
    hdr = (f"<!-- Public mirror. Source of truth: szl-holdings/szl-org-health docs/PYPI_RELEASE_PATH.md (private repository), "
           f"commit {sha}, mirrored {now}. Refresh with tools/mirror_pypi_governance.py from a checkout that can read the source repository. -->\n\n")
    (ROOT / "pypi/release-path.md").write_text(hdr + doc, encoding="utf-8")
    meta = json.loads((ROOT / "pypi/MIRROR.json").read_text())
    meta.update(source_commit=sha, mirrored_at=now)
    (ROOT / "pypi/MIRROR.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"mirrored {len(FILES) + 1} files from {sha[:12]} at {now}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
