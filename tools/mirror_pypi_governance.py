#!/usr/bin/env python3
"""Refresh pypi/ from a local checkout of szl-holdings/szl-org-health. Standard library only.

Usage: python3 tools/mirror_pypi_governance.py /path/to/szl-org-health
Projects only published package identities into a public manifest (never copies private hold or queue rows),
copies the canonical workflow/gate/generator byte-for-byte, prefixes release-path.md with provenance,
and records the immutable private source commit and observation time in MIRROR.json.
"""
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
# The site fixture runs tools under python -I; import only this checked-out tool directory.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from public_pypi_projection import public_projection  # noqa: E402 - pinned sibling module

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = {
    "canonical/publish-pypi.yml": "governance/pypi/canonical/publish-pypi.yml",
    "canonical/szl_pypi_release_gate.py": "governance/pypi/canonical/szl_pypi_release_gate.py",
    "canonical/gen_publish_workflow.py": "governance/pypi/canonical/gen_publish_workflow.py",
}

def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    src = pathlib.Path(sys.argv[1]).resolve()
    sha = subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(src), "status", "--porcelain"], text=True).strip():
        raise SystemExit("refusing to mirror a dirty source checkout")
    # Even a clean checkout may have Windows EOL translations. The committed
    # Git object, not the platform-specific checkout, owns the source evidence.
    manifest_raw = subprocess.check_output(
        ["git", "-C", str(src), "show", f"{sha}:governance/pypi/pypi-packages.v1.json"]
    )
    public_manifest = public_projection(manifest_raw, sha)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_sha256 = {}
    for dst, rel in FILES.items():
        payload = subprocess.check_output(
            ["git", "-C", str(src), "show", f"{sha}:{rel}"]
        )
        path = ROOT / "pypi" / dst
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        source_sha256[dst] = hashlib.sha256(payload).hexdigest()
    (ROOT / "pypi/pypi-packages.v1.json").write_bytes(public_manifest)
    doc = subprocess.check_output(
        ["git", "-C", str(src), "show", f"{sha}:docs/PYPI_RELEASE_PATH.md"]
    ).decode("utf-8")
    hdr = (f"<!-- Public mirror. Source of truth: szl-holdings/szl-org-health docs/PYPI_RELEASE_PATH.md (private repository), "
           f"commit {sha}, mirrored {now}. Refresh with tools/mirror_pypi_governance.py from a checkout that can read the source repository. -->\n\n")
    (ROOT / "pypi/release-path.md").write_text(
        hdr + doc, encoding="utf-8", newline="\n"
    )
    meta = json.loads((ROOT / "pypi/MIRROR.json").read_text(encoding="utf-8"))
    meta.update(
        source_commit=sha,
        mirrored_at=now,
        public_manifest_projection="szl.public-pypi-projection/v1",
        source_sha256=source_sha256,
        public_projection_sha256=hashlib.sha256(public_manifest).hexdigest(),
        note="Public manifest contains published packages only; held, internal, never, third-party and queued identities are omitted. Canonical workflow/gate/generator remain byte-for-byte mirrors; release-path.md is prefixed with provenance. Private canonical source remains authoritative.",
    )
    (ROOT / "pypi/MIRROR.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"mirrored {len(FILES) + 2} files from {sha[:12]} at {now}; published-only projection")
    return 0

if __name__ == "__main__":
    sys.exit(main())
