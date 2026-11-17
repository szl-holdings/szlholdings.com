#!/usr/bin/env python3
"""Refresh pypi/ from a local checkout of szl-holdings/szl-org-health. Standard library only.

Usage: python3 tools/mirror_pypi_governance.py /path/to/szl-org-health
Projects only published package identities into a public manifest (never copies private hold or queue rows),
copies the canonical workflow/gate/generator byte-for-byte, prefixes release-path.md with provenance,
and records the immutable private source commit and observation time in MIRROR.json.
"""
import datetime, json, pathlib, shutil, subprocess, sys
# The site fixture runs tools under python -I; import only this checked-out tool directory.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from public_pypi_projection import public_projection

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = {
    "canonical/publish-pypi.yml": "governance/pypi/canonical/publish-pypi.yml",
    "canonical/szl_pypi_release_gate.py": "governance/pypi/canonical/szl_pypi_release_gate.py",
    "canonical/gen_publish_workflow.py": "governance/pypi/canonical/gen_publish_workflow.py",
}

def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__); return 2
    src = pathlib.Path(sys.argv[1]).resolve()
    sha = subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(src), "status", "--porcelain"], text=True).strip():
        raise SystemExit("refusing to mirror a dirty source checkout")
    manifest_raw = (src / "governance/pypi/pypi-packages.v1.json").read_bytes()
    public_manifest = public_projection(manifest_raw, sha)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for dst, rel in FILES.items():
        (ROOT / "pypi" / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, ROOT / "pypi" / dst)
    (ROOT / "pypi/pypi-packages.v1.json").write_bytes(public_manifest)
    doc = (src / "docs/PYPI_RELEASE_PATH.md").read_text(encoding="utf-8")
    hdr = (f"<!-- Public mirror. Source of truth: szl-holdings/szl-org-health docs/PYPI_RELEASE_PATH.md (private repository), "
           f"commit {sha}, mirrored {now}. Refresh with tools/mirror_pypi_governance.py from a checkout that can read the source repository. -->\n\n")
    (ROOT / "pypi/release-path.md").write_text(hdr + doc, encoding="utf-8")
    meta = json.loads((ROOT / "pypi/MIRROR.json").read_text())
    meta.update(source_commit=sha, mirrored_at=now, public_manifest_projection="szl.public-pypi-projection/v1",
                note="Public manifest contains published packages only; held, internal, never, third-party and queued identities are omitted. Canonical workflow/gate/generator remain byte-for-byte mirrors; release-path.md is prefixed with provenance. Private canonical source remains authoritative.")
    (ROOT / "pypi/MIRROR.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"mirrored {len(FILES) + 2} files from {sha[:12]} at {now}; published-only projection")
    return 0

if __name__ == "__main__":
    sys.exit(main())
