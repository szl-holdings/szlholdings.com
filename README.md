# szlholdings.com

Company domain-of-record page for SZL Holdings, served by GitHub Pages from this repository.

- Hostname: `szlholdings.com` (see `CNAME`); `www.szlholdings.com` redirects here once its CNAME exists.
- Content: one page (`index.html`), `404.html`, `robots.txt`, `sitemap.xml`, `.well-known/security.txt`.
- No build step, no external requests (system fonts, inline CSS). `.nojekyll` keeps `.well-known/` served.

## DNS contract (zone at Squarespace Domains, Google Cloud DNS nameservers)

| Record | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` |
| AAAA (optional) | `@` | `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153` |
| CNAME | `www` | `szl-holdings.github.io` |
| MX / TXT (SPF, DKIM) | `@`, `google._domainkey` | unchanged, Google Workspace |

Repository settings → Pages → custom domain `szlholdings.com`, then **Enforce HTTPS** once the certificate is issued.

## /pypi/ public mirror

`pypi/` holds byte-identical copies of the PyPI governance artifacts (manifest, release contract, canonical workflow,
gate and generator) from the private `szl-holdings/szl-org-health` repository, plus `MIRROR.json` with the source
commit. Refresh from a checkout that can read the source:

```
python3 tools/mirror_pypi_governance.py /path/to/szl-org-health
```

## Refreshing the package table

```
python3 tools/render_packages.py
```

reads `pypi/pypi-packages.v1.json` (the mirror) and rewrites the rows between the
`packages:start` / `packages:end` markers plus the read-date sentence. Commit the result through a pull request.

## Claims policy

Everything on the page is checkable: links resolve to the GitHub organization, the Hugging Face organization,
PyPI project pages and the live product. Nothing here asserts a result that is not published elsewhere with evidence.
