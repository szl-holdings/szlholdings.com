#!/usr/bin/env python3
"""Refresh the PyPI package table in index.html from the szl-org-health manifest.

Usage:  python3 tools/render_packages.py [--manifest PATH_OR_HTTPS_URL] [--check]
Reads the manifest (default: the public mirror at pypi/pypi-packages.v1.json; pass --manifest for another copy),
rewrites the rows between <!-- packages:start --> and <!-- packages:end -->, the queued list, and the
"read from the PyPI JSON and Simple APIs on YYYY-MM-DD" date above the table. Standard library only.

The date is the manifest's own `generated_at` (when the szl-org-health audit read PyPI), never the day this
script runs: re-rendering unchanged data must not make the page claim a fresher read than the one it shows.
"""
import argparse
import datetime
import html
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT = str(ROOT / "pypi" / "pypi-packages.v1.json")  # public mirror of szl-org-health governance/pypi


def load(src):
    if src.startswith("https://"):
        with urllib.request.urlopen(src, timeout=30) as r:
            return json.load(r)
    if src.startswith("http://"):
        raise SystemExit(f"refusing to read the manifest over plain HTTP: {src}")
    return json.loads(pathlib.Path(src).read_text(encoding="utf-8"))


def read_date(manifest):
    """YYYY-MM-DD of the manifest's generated_at: the day its audit read the PyPI APIs."""
    raw = manifest.get("generated_at")
    if not isinstance(raw, str):
        raise SystemExit("manifest has no generated_at; refusing to date the package table")
    return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()


def sub_once(pattern, repl, text, what, flags=0):
    out, n = re.subn(pattern, repl, text, flags=flags)
    if n != 1:
        raise SystemExit(f"index.html: expected exactly one {what}, found {n}; fix the page before rendering")
    return out


def render(manifest, page_text):
    pub = sorted((p for p in manifest["packages"] if p.get("status") == "published"), key=lambda p: p["name"])
    queued = sorted((p for p in manifest["packages"] if p.get("status") == "queued"), key=lambda p: p["name"])
    rows = []
    for p in pub:
        rows.append("        <tr>\n"
                    f'          <td><a href="{html.escape(p["pypi_url"])}">{html.escape(p["name"])}</a></td>\n'
                    f'          <td class="num">{html.escape(str(p.get("pypi_version") or ""))}</td>\n'
                    f'          <td><a href="{html.escape(p["source"])}">szl-holdings/{html.escape(p["repo"])}</a></td>\n'
                    "        </tr>")
    date = read_date(manifest)
    t = sub_once(r"<!-- packages:start -->.*?<!-- packages:end -->",
                 lambda _m: "<!-- packages:start -->\n" + "\n".join(rows) + "\n<!-- packages:end -->",
                 page_text, "packages:start/packages:end block", flags=re.S)
    t = sub_once(r"Simple APIs on \d{4}-\d{2}-\d{2}", lambda _m: f"Simple APIs on {date}", t,
                 "'Simple APIs on YYYY-MM-DD' read date")
    t = sub_once(r"(Queued for first release through the same path: ).*?\.</p>",
                 lambda mm: mm.group(1) + html.escape(", ".join(p["name"] for p in queued)) + ".</p>",
                 t, "queued-packages sentence", flags=re.S)
    return t, len(pub), len(queued), date


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default=DEFAULT)
    ap.add_argument("--check", action="store_true", help="exit 2 if index.html would change (no write)")
    a = ap.parse_args(argv)
    m = load(a.manifest)
    page = ROOT / "index.html"
    t = page.read_text(encoding="utf-8")
    t2, n_pub, n_queued, date = render(m, t)
    if t2 == t:
        print("index.html unchanged")
        return 0
    if a.check:
        print("DRIFT: the package table, queued list or read date no longer matches the manifest; "
              "run tools/render_packages.py")
        return 2
    page.write_text(t2, encoding="utf-8")
    print(f"index.html updated: {n_pub} published, {n_queued} queued, read date {date} (manifest generated_at)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
