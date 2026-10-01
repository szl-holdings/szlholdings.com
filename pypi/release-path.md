<!-- Public mirror. Source of truth: szl-holdings/szl-org-health docs/PYPI_RELEASE_PATH.md (private repository), commit a2d221ae40c9fd0ab21f8821a7433e98b74d2ed0, mirrored 2026-10-01T19:18:43Z. Refresh with tools/mirror_pypi_governance.py from a checkout that can read the source repository. -->

# PyPI release path — contract `szl.pypi-release.v2`

One organization owns every SZL package on PyPI. One workflow shape publishes them. One credential
type exists (a short-lived GitHub OIDC token), and it exists only inside the `publish` job of a run
triggered by a GitHub Release on an admin-created tag. Everything else is enforced by the index, by
GitHub, or by the fail-closed gate — not by convention.

## Source of truth

`governance/pypi/pypi-packages.v1.json` lists every `pyproject.toml` in the estate with a status:

| status | meaning | enforcement |
|---|---|---|
| `published` | live on PyPI from the canonical workflow | audit: canonical bytes, provenance, verified source URL, tag at attested commit |
| `queued` | canonical workflow installed, inert until a Release is published and an org-level pending publisher exists | audit: canonical bytes, controls present, project absent on PyPI |
| `hold` | owner decision or layout defect recorded in `reason`; no workflow | manifest only |
| `internal` / `never` | monorepo-internal, duplicate copy, Kernel Hub or Space descriptor | `Private :: Do Not Upload` classifier — PyPI rejects the upload itself |
| `third-party` | vendored upstream project | never ours to publish |

Changing a status is a reviewed edit to this file. The nightly audit (`pypi-release-path-audit.yml`)
fails on any drift between the manifest and live GitHub + PyPI state.

## The release path

1. Bump `[project].version` on `main`.
2. `gh release create v<version> --generate-notes` (multi-package repositories: `<package>-v<version>`).
3. `publish-pypi.yml` → `build` job runs `.github/scripts/szl_pypi_release_gate.py`:
   tag == version · explicit PEP 517 backend · description/readme/license/requires-python present ·
   `[project.urls]` Source on `github.com/szl-holdings/<repo>` · `twine check --strict` · exactly one
   wheel + one sdist · wheel has Python files and no `tests`/`data`/`scripts` top-level leaks ·
   `[tool.szl.release].import_names` equals the wheel's top level · version not already on PyPI ·
   isolated install + import smoke test · SHA-256 receipt.
4. `publish` job (environment `pypi`, `id-token: write`) uploads through Trusted Publishing with
   PEP 740 attestations. `skip-existing: false`: a duplicate version is a release error.

`pull_request` and `push` runs execute step 3 only, so release readiness is visible on every PR.

## GitHub controls (per publishing repository)

- Environment `pypi` (or the declared name): custom deployment policy, release tags only (`v*`).
- Tag ruleset `pypi-release-tags`: create/update/delete of `refs/tags/v*` restricted to repository
  admins (organization admins bypass). Tags are therefore an admin act, and so is a release.
- Default-branch protection remains the estate baseline.
- All actions SHA-pinned; `permissions: {}` at workflow level, least privilege per job.

## PyPI controls (organization `szl-holdings`)

- Organization owns every project; the founder account and a second owner account are org Owners.
  Team `release-managers` (Maintainer role) can be granted per project without sharing credentials.
- Each project has exactly one Trusted Publisher: GitHub · `szl-holdings/<repo>` · `publish-pypi.yml`
  · environment `pypi` (or the declared one). No API tokens exist on any account.
- New packages are registered as organization-level pending publishers so the project is owned by the
  organization from its first upload.
- 2FA is mandatory on PyPI for every account that uploads or manages projects; Trusted Publishing
  removes the need for tokens entirely.
- Verified details: because uploads come through the GitHub Trusted Publisher, PyPI marks
  `https://github.com/szl-holdings/<repo>` links as verified, which is how a buyer confirms the
  organizational owner matches the source.

## Why this is not a bandaid

- Backfilled tags were placed on the exact commits named in PyPI's own Sigstore attestations; the
  audit re-derives those digests from the certificates every night.
- `Private :: Do Not Upload` moves the "never publish this" decision from a comment to a rule the
  index enforces.
- Dangling dependencies on the retired `szl-receipt` distribution name were repointed to
  `szl-receipt-dsse` wherever a PyPI extra referenced them.
- The gate forbids empty wheels, leaked test packages, and unverified source URLs — the three defects
  the 2026-09-30 audit found in the queued set.

## Known holds (owner decisions)

See `reason` fields in the manifest: `szl-forge-inference` and `szl-second-brain` (layout),
`szl-brand` (assets, CC-BY-4.0), `gdw-frontier` and `defensive-control-plane` (private sources),
`nexus-dynamics` (lab binding). Each needs a decision, not a workaround.
