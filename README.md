# szlholdings.com

<!-- szl:header v1 -->
<!-- Native identity: szl-brand@4309f6fce89179331b0b3ed8c99494e76c5be256; Orbit v2 icon. -->
<p>
  <a href="https://github.com/szl-holdings">
    <img src="https://raw.githubusercontent.com/szl-holdings/szl-brand/4309f6fce89179331b0b3ed8c99494e76c5be256/kit/logos/orbit-v2/suite/szl-icon-32.svg" alt="SZL Holdings — Orbit v2" width="32" height="32" />
  </a>
</p>

**Control before action. Evidence after.**

[Product](https://a-11-oy.com) · [Proof](https://a11oy.net) · [GitHub organization](https://github.com/szl-holdings)
<!-- /szl:header -->

Company domain-of-record page for SZL Holdings, served by GitHub Pages from the root of this repository.

- Hostname: `szlholdings.com` (see `CNAME`); `www.szlholdings.com` redirects here once its CNAME exists.
- Content: the home page (`index.html`), the [`/pypi/`](pypi/index.html) mirror page described below, `404.html`,
  `robots.txt`, `sitemap.xml` and `.well-known/security.txt`.
- No build step at deploy time and no external requests (system fonts, inline CSS); the tools in `tools/` are
  standard-library Python. `.nojekyll` keeps `.well-known/` served.
- Pages publishes the repository root as-is, so every tracked file is public. `.gitignore` keeps bytecode and build
  output out of the tree.

## Status (2026-11-06): domain not yet on GitHub Pages

The Pages build deploys, but the apex `A` record at the current DNS host (Google Cloud DNS; registrar Squarespace
Domains) points at `34.111.179.208`, not GitHub Pages, so `https://szlholdings.com/` does not serve this page. The
`live` job in `verify` (Mondays and on manual dispatch) fails closed until it does
([last run, 2026-11-04](https://github.com/szl-holdings/szlholdings.com/actions/runs/41861152725):
`curl: (35) TLS connect error`).
A Cloudflare zone holding the records below (all DNS-only) is staged and waits for the nameserver switch.

## DNS contract

| Record | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` |
| AAAA (optional) | `@` | `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153` |
| CNAME | `www` | `szl-holdings.github.io` |
| MX / TXT (SPF, DKIM) | `@`, `google._domainkey` | unchanged, Google Workspace |
| TXT (DMARC) | `_dmarc` | `v=DMARC1; p=none` (monitor-only) in the staged Cloudflare zone |

The Pages records must stay **DNS-only** (not proxied): GitHub issues the certificate only when the hostname resolves
to its own addresses. Cut-over, in order:

1. Squarespace Domains → `szlholdings.com` → nameservers: the two Cloudflare nameservers shown for the staged zone
   (or set the records above at the current DNS host instead).
2. Repository settings → Pages: the custom domain is already `szlholdings.com` (the Pages deploy reports the
   environment URL `http://szlholdings.com/`); once GitHub has issued the certificate, tick **Enforce HTTPS**.
3. Actions → `verify` → *Run workflow*: the `live` job must pass (`live: page and security.txt served over HTTPS`).

## /pypi/ public mirror

`pypi/` holds copies of the PyPI governance artifacts from the private `szl-holdings/szl-org-health` repository: the
manifest, canonical workflow, gate and generator byte-for-byte, and the release contract (`release-path.md`) with a
provenance comment prepended. `MIRROR.json` records the source commit and the mirror time. The mirror is refreshed by
hand, so it can trail the source. Refresh from a checkout that can read the source:

```
python3 tools/mirror_pypi_governance.py /path/to/szl-org-health
```

## Refreshing the package table

```
python3 tools/render_packages.py
```

reads `pypi/pypi-packages.v1.json` (the mirror) and rewrites the rows between the `packages:start` /
`packages:end` markers, the queued list and the read date. The read date is the manifest's `generated_at` (when the
szl-org-health audit read PyPI), so re-rendering unchanged data never re-dates the page. `--check` exits 2 on drift
without writing. Commit the result through a pull request.

## Verify locally

Standard library only, nothing to install:

```
python3 tools/verify_site.py               # structural checks: markup, no third-party requests, local links, sitemap, CNAME, security.txt
python3 tools/render_packages.py --check   # the package table matches the mirrored manifest
python3 -m unittest discover -s tests -v   # tests for the three tools and repository hygiene
```

With pytest instead: `python3 -m pip install -e '.[test]' && python3 -m pytest`. `pyproject.toml` describes no
installable package; it only provides that test environment and is marked `Private :: Do Not Upload`.

CI: `verify` runs the structural checks and the unit tests on every push and pull request (`structural`), and the
drift check and the live HTTPS probe every Monday (`drift`, `live`). `CodeQL` analyses Python and the workflows through
the organization's SHA-pinned reusable workflow.

## Claims policy and proof boundary

Everything on the page is checkable: links resolve to the GitHub organization, the Hugging Face organization,
PyPI project pages and the live product. Nothing here asserts a result that is not published elsewhere with evidence.

What the checks prove: the committed page is well-formed, loads nothing from third parties, its local links and sitemap
URLs resolve, its package table equals the mirrored manifest, and `security.txt` is current. What they do not prove:
that `https://szlholdings.com/` serves this page (only the `live` job measures that), that the table matches PyPI today
(it shows the manifest's read date; newer releases may exist), that external sites are up, or the organization-profile
statements on the page (two-factor requirement, contact address), which CI cannot read.

Estate on Hugging Face: models, datasets and Spaces are published under the [SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS) org.

## License

Apache-2.0 — see [LICENSE](LICENSE).
