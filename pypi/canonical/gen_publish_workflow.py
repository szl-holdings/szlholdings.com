#!/usr/bin/env python3
"""Generate the canonical szl-holdings `publish-pypi.yml` for a repository.

Usage: gen_workflow.py "name=dir[:env];name2=dir2[:env]"  -> prints YAML
"""
import sys

# SHA pins. The version is written on the comment line ABOVE each `uses:` so that
# estate verifiers which require `uses:` lines to end at the 40-hex SHA still pass.
PINS = {
    "checkout": ("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
    "setup_python": ("actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", "v7.0.0"),
    "upload": ("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", "v7.0.1"),
    "download": ("actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c", "v8.0.1"),
    "publish": ("pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33", "v1.14.2"),
}


def use(key: str, indent: int, name: str | None = None) -> str:
    ref, ver = PINS[key]
    pad = " " * indent
    lines = [f"{pad}# {ref.split('@')[0]} {ver}"]
    if name:
        lines.append(f"{pad}- name: {name}")
        lines.append(f"{pad}  uses: {ref}")
    else:
        lines.append(f"{pad}- uses: {ref}")
    return "\n".join(lines)


def parse(spec):
    pkgs = []
    for item in [s.strip() for s in spec.split(";") if s.strip()]:
        name, _, rest = item.partition("=")
        d, _, env = rest.partition(":")
        pkgs.append({"name": name.strip(), "dir": (d or ".").strip(), "environment": (env or "pypi").strip()})
    return pkgs


def render(spec: str) -> str:
    pkgs = parse(spec)
    multi = len(pkgs) > 1
    tag_rule = "`<package>-v<version>` (this repository declares more than one package)" if multi else "`v<version>`"
    head = f"""name: publish to PyPI

# SZL Holdings canonical PyPI release path (szl.pypi-release.v2).
#
# Release path (the ONLY one):
#   1. Bump [project].version in pyproject.toml on main.
#   2. Publish a GitHub Release whose tag is {tag_rule}.
#   3. This workflow builds, gates, and publishes through PyPI Trusted
#      Publishing (OIDC). No API token exists anywhere in this estate.
#
# Owner-side registration (once per package, on pypi.org):
#   Publisher: GitHub  Owner: szl-holdings  Repository: <this repo>
#   Workflow: publish-pypi.yml  Environment: <see SZL_PACKAGES below>
#   For a package that does not exist yet, register it as a PENDING publisher
#   at the organization level so the project is owned by the org on creation.
#
# pull_request / push runs exercise the same build + gate (release readiness)
# and never publish. The `publish` job runs only for `release: published`.
#
# Edit SZL_PACKAGES only. Everything else is canonical; the org health audit
# compares this file and .github/scripts/szl_pypi_release_gate.py by hash.

on:
  release:
    types: [published]
  pull_request:
    paths:
      - "pyproject.toml"
      - "**/pyproject.toml"
      - ".github/workflows/publish-pypi.yml"
      - ".github/scripts/szl_pypi_release_gate.py"
      - "src/**"
      - "**/*.py"
  push:
    branches: [main]
    paths:
      - "pyproject.toml"
      - "**/pyproject.toml"
      - ".github/workflows/publish-pypi.yml"
      - ".github/scripts/szl_pypi_release_gate.py"

env:
  # name=directory[:github-environment]; separate packages with ';'
  SZL_PACKAGES: "{spec}"

permissions: {{}}

concurrency:
  group: publish-pypi-${{{{ github.event_name }}}}-${{{{ github.ref }}}}
  cancel-in-progress: false

jobs:
  build:
    name: Build and gate distributions
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      contents: read
    outputs:
      package: ${{{{ steps.gate.outputs.package }}}}
      version: ${{{{ steps.gate.outputs.version }}}}
      environment: ${{{{ steps.gate.outputs.environment }}}}
    steps:
{use('checkout', 6)}
        with:
          persist-credentials: false
{use('setup_python', 6)}
        with:
          python-version: "3.12"
      - name: Install build tooling
        run: python -m pip install --disable-pip-version-check --upgrade "build>=1.2" "twine>=6.1"
      - name: Release gate (build, verify metadata, bind tag to version)
        id: gate
        run: >-
          python .github/scripts/szl_pypi_release_gate.py
          --packages "$SZL_PACKAGES"
          --repo "${{{{ github.repository }}}}"
          --event "${{{{ github.event_name }}}}"
          --ref-type "${{{{ github.ref_type }}}}"
          --ref-name "${{{{ github.ref_name }}}}"
          --outdir dist
{use('upload', 6, 'Upload release-gate receipt')}
        with:
          name: release-gate-receipt
          path: release-gate.json
          if-no-files-found: error
      # actions/upload-artifact v7.0.1
      - name: Upload distributions (release only)
        if: github.event_name == 'release'
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        with:
          name: pypi-dists
          path: |
            dist/*.whl
            dist/*.tar.gz
          if-no-files-found: error
"""
    jobs = []
    for p in pkgs:
        job_id = "publish" if not multi else "publish-" + p["name"].lower().replace(".", "-").replace("_", "-")
        cond = "github.event_name == 'release'"
        if multi:
            cond += f" && needs.build.outputs.package == '{p['name']}'"
        jobs.append(f"""
  {job_id}:
    name: Publish {p['name']} to PyPI (Trusted Publishing)
    needs: build
    if: {cond}
    runs-on: ubuntu-latest
    timeout-minutes: 15
    environment:
      name: {p['environment']}
      url: https://pypi.org/project/{p['name']}/${{{{ needs.build.outputs.version }}}}/
    permissions:
      id-token: write   # OIDC token for PyPI Trusted Publishing — the only credential
      contents: read
    steps:
{use('download', 6, 'Download gated distributions')}
        with:
          name: pypi-dists
          path: dist/
{use('publish', 6, 'Publish to PyPI')}
        with:
          packages-dir: dist/
          attestations: true     # PEP 740 provenance, signed via Sigstore
          verify-metadata: true
          skip-existing: false   # a duplicate version is a release error, never a silent skip
          print-hash: true
""")
    return head + "".join(jobs)


if __name__ == "__main__":
    sys.stdout.write(render(sys.argv[1]))
