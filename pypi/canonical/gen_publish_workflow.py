#!/usr/bin/env python3
"""Generate the canonical szl-holdings `publish-pypi.yml` for a repository.

Usage: gen_workflow.py "name=dir[:env];name2=dir2[:env]"  -> prints YAML
       gen_workflow.py --transport-probe  -> prints szl-org-health's own
       .github/workflows/pypi-artifact-transport.yml (same PINS, never publishes)
"""
import sys

# SHA pins: the ONLY definition of every action reference in the workflow. Each
# `uses:` line, and the version comment written on the line ABOVE it (so estate
# verifiers which require `uses:` lines to end at the 40-hex SHA still pass), is
# rendered from this table by use(). Never write an action SHA or its version
# comment as a literal in the template: both artifact uploads and every download
# must move together when a pin changes.
PINS = {
    "checkout": ("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
    "setup_python": ("actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0", "v7.1.0"),
    "upload": ("actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9", "v7.0.2"),
    "download": ("actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333", "v8.0.2"),
    "publish": ("pypa/gh-action-pypi-publish@7245906fb61fa33a13554f9d5fb856fe61758086", "v1.14.3"),
}


def use(key: str, indent: int, name: str | None = None, condition: str | None = None) -> str:
    ref, ver = PINS[key]
    pad = " " * indent
    lines = [f"{pad}# {ref.split('@')[0]} {ver}"]
    if name:
        lines.append(f"{pad}- name: {name}")
        if condition:
            lines.append(f"{pad}  if: {condition}")
        lines.append(f"{pad}  uses: {ref}")
    else:
        if condition:
            raise ValueError("a conditional step must be named")
        lines.append(f"{pad}- uses: {ref}")
    return "\n".join(lines)


def parse(spec):
    pkgs = []
    for item in [s.strip() for s in spec.split(";") if s.strip()]:
        name, _, rest = item.partition("=")
        d, _, env = rest.partition(":")
        pkgs.append({"name": name.strip(), "dir": (d or ".").strip(), "environment": (env or "pypi").strip()})
    return pkgs


# Repository-specific security contracts are canonical, not disposable hand edits.
# Unknown ordinary packages retain the byte-identical default release path.
RELEASE_PROFILES = {
    "szl-provctl": {"build_lock": "requirements/ci/pypi-release.txt", "sbom": False},
    "szl-evidence-mandate": {"build_lock": "requirements/ci/pypi-release.txt", "sbom": True},
}


def apply_release_profile(workflow: str, packages: list[dict]) -> str:
    """Preserve admitted release controls for the two explicit consumers.

    No arbitrary shell/YAML extension is accepted. A recognized package in a
    different layout/environment or a changed template fails closed rather than
    silently dropping its security requirements. Other renders stay unchanged.
    """
    matches = [p for p in packages if p["name"] in RELEASE_PROFILES]
    if not matches:
        return workflow
    if len(packages) != 1 or packages[0]["dir"] != "." or packages[0]["environment"] != "pypi":
        raise ValueError("release security profile requires one root package in pypi")
    profile = RELEASE_PROFILES[matches[0]["name"]]
    install = 'python -m pip install --disable-pip-version-check --upgrade "build>=1.2" "twine>=6.1"'
    if workflow.count(install) != 1:
        raise ValueError("canonical build-tooling anchor changed")
    workflow = workflow.replace(
        install,
        "python -m pip install --disable-pip-version-check --require-hashes -r " + profile["build_lock"],
        1,
    )
    anchor = '      - ".github/scripts/szl_pypi_release_gate.py"\n'
    if workflow.count(anchor) != 2:
        raise ValueError("canonical release trigger anchors changed")
    paths = ["requirements/ci/pypi-release.in", profile["build_lock"]]
    if profile["sbom"]:
        paths.append(".github/scripts/szl_pypi_sbom.py")
    workflow = workflow.replace(anchor, anchor + "".join(f'      - "{path}"\n' for path in paths))
    if profile["sbom"]:
        marker = "\n  publish:\n"
        if workflow.count(marker) != 1:
            raise ValueError("canonical single-package publish anchor changed")
        steps = """      - name: Generate CycloneDX SBOM
        run: >-
          python .github/scripts/szl_pypi_sbom.py generate
          --dist dist
          --pyproject pyproject.toml
          --outdir sbom
          --venv "$RUNNER_TEMP/sbom-venv"
""" + use("upload", 6, "Upload CycloneDX SBOM") + """
        with:
          name: cyclonedx-sbom
          path: sbom/
          if-no-files-found: error
          retention-days: 90
"""
        workflow = workflow.replace(marker, steps + marker, 1)
    return workflow


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
{use('upload', 6, 'Upload distributions (release only)', "github.event_name == 'release'")}
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
    return apply_release_profile(head + "".join(jobs), pkgs)


TRANSPORT_PROBE_PATH = ".github/workflows/pypi-artifact-transport.yml"


def render_transport_probe() -> str:
    """szl-org-health's own non-publishing check of the release artifact pins.

    The canonical workflow uploads `pypi-dists` with PINS["upload"] and downloads it
    with PINS["download"] only on `release: published`, so ordinary PR/push runs
    never exercise the download pin. This workflow moves two inert files through the
    same pins, with the same artifact name, paths and inputs, and checks the bytes.
    """
    return f"""name: PyPI artifact transport probe

# Non-publishing qualification of the canonical publish-pypi.yml artifact pins.
# Rendered by governance/pypi/canonical/gen_publish_workflow.py
# (render_transport_probe) from the same PINS table as the canonical release
# workflow; tests/test_pypi_artifact_transport.py fails on any hand edit.
#
# Two deterministic inert files (a dummy wheel and sdist classified
# `Private :: Do Not Upload`) travel from `stage` to `fetch` as artifact
# `pypi-dists`, exactly as the release job's distributions do. `fetch` requires
# byte-identical SHA-256 before and after transport and rejects missing, extra
# or altered files. No id-token, no secrets, no environment, no publish step.

on:
  pull_request:
    paths:
      - "governance/pypi/canonical/**"
      - "tools/pypi_artifact_transport.py"
      - "{TRANSPORT_PROBE_PATH}"
  push:
    branches: [main]
    paths:
      - "governance/pypi/canonical/**"
      - "tools/pypi_artifact_transport.py"
      - "{TRANSPORT_PROBE_PATH}"

permissions: {{}}

concurrency:
  group: pypi-artifact-transport-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  stage:
    name: Stage inert distributions
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    outputs:
      manifest: ${{{{ steps.stage.outputs.manifest }}}}
    steps:
{use('checkout', 6)}
        with:
          persist-credentials: false
      - name: Build two inert files and record their SHA-256
        id: stage
        run: |
          python3 -I tools/pypi_artifact_transport.py stage --outdir dist --manifest "$RUNNER_TEMP/transport-manifest.json"
          echo "manifest=$(cat "$RUNNER_TEMP/transport-manifest.json")" >> "$GITHUB_OUTPUT"
{use('upload', 6, 'Upload inert distributions')}
        id: upload
        with:
          name: pypi-dists
          path: |
            dist/*.whl
            dist/*.tar.gz
          if-no-files-found: error
          retention-days: 1
      - name: Record the uploaded artifact digest
        env:
          ARTIFACT_ID: ${{{{ steps.upload.outputs.artifact-id }}}}
          ARTIFACT_DIGEST: ${{{{ steps.upload.outputs.artifact-digest }}}}
        run: |
          echo "artifact-id=$ARTIFACT_ID"
          echo "artifact-digest=sha256:$ARTIFACT_DIGEST"
          test -n "$ARTIFACT_ID"
          echo "$ARTIFACT_DIGEST" | grep -Eq '^[0-9a-f]{{64}}$'
{use('upload', 6, 'Negative control - upload of a missing expected file is rejected')}
        id: missing_upload
        continue-on-error: true
        with:
          name: pypi-dists-missing-file-probe
          path: dist/missing-expected-file.whl
          if-no-files-found: error
          retention-days: 1
      - name: Assert the missing-file upload failed
        env:
          OUTCOME: ${{{{ steps.missing_upload.outcome }}}}
        run: |
          echo "missing-file upload outcome=$OUTCOME"
          test "$OUTCOME" = failure

  fetch:
    name: Download and verify inert distributions
    needs: stage
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
{use('checkout', 6)}
        with:
          persist-credentials: false
{use('download', 6, 'Download inert distributions')}
        with:
          name: pypi-dists
          path: dist/
          digest-mismatch: error
      - name: Verify pre/post SHA-256 equality
        env:
          MANIFEST: ${{{{ needs.stage.outputs.manifest }}}}
        run: python3 -I tools/pypi_artifact_transport.py verify --dir dist --manifest-json "$MANIFEST"
      - name: Negative controls - missing, extra and altered files are rejected
        env:
          MANIFEST: ${{{{ needs.stage.outputs.manifest }}}}
        run: python3 -I tools/pypi_artifact_transport.py self-check --dir dist --manifest-json "$MANIFEST"
"""


if __name__ == "__main__":
    if sys.argv[1:] == ["--transport-probe"]:
        sys.stdout.write(render_transport_probe())
    else:
        sys.stdout.write(render(sys.argv[1]))
