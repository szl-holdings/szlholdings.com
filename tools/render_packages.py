#!/usr/bin/env python3
"""Refresh the PyPI package table in index.html from the szl-org-health manifest.

Usage:  python3 tools/render_packages.py [--manifest PATH_OR_URL]
Reads governance/pypi/pypi-packages.v1.json (default: raw file on szl-org-health main),
rewrites the rows between <!-- packages:start --> and <!-- packages:end -->, and updates the
"read ... on YYYY-MM-DD" date in the paragraph above the table. Standard library only.
"""
import argparse, datetime, html, json, pathlib, re, sys, urllib.request

DEFAULT = "https://raw.githubusercontent.com/szl-holdings/szl-org-health/main/governance/pypi/pypi-packages.v1.json"

def load(src):
    if src.startswith("http"):
        with urllib.request.urlopen(src, timeout=30) as r:
            return json.load(r)
    return json.loads(pathlib.Path(src).read_text())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=DEFAULT)
    a = ap.parse_args()
    m = load(a.manifest)
    pub = sorted((p for p in m["packages"] if p.get("status") == "published"), key=lambda p: p["name"])
    queued = sorted((p for p in m["packages"] if p.get("status") == "queued"), key=lambda p: p["name"])
    rows = []
    for p in pub:
        rows.append("        <tr>\n"
                    f'          <td><a href="{html.escape(p["pypi_url"])}">{html.escape(p["name"])}</a></td>\n'
                    f'          <td class="num">{html.escape(str(p.get("pypi_version") or ""))}</td>\n'
                    f'          <td><a href="{html.escape(p["source"])}">szl-holdings/{html.escape(p["repo"])}</a></td>\n'
                    "        </tr>")
    page = pathlib.Path(__file__).resolve().parent.parent / "index.html"
    t = page.read_text()
    t2 = re.sub(r"<!-- packages:start -->.*?<!-- packages:end -->",
                "<!-- packages:start -->\n" + "\n".join(rows) + "\n<!-- packages:end -->", t, flags=re.S)
    today = datetime.date.today().isoformat()
    t2 = re.sub(r"Simple APIs on \d{4}-\d{2}-\d{2}", f"Simple APIs on {today}", t2)
    t2 = re.sub(r"(Queued for first release through the same path: ).*?\.</p>",
                lambda mm: mm.group(1) + html.escape(", ".join(p["name"] for p in queued)) + ".</p>", t2, flags=re.S)
    if t2 == t:
        print("index.html unchanged"); return 0
    page.write_text(t2)
    print(f"index.html updated: {len(pub)} published, {len(queued)} queued, dated {today}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
