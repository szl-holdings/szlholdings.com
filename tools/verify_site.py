#!/usr/bin/env python3
"""Structural checks for the szlholdings.com page. Standard library only; exit 1 on any failure.

Checks the published tree as GitHub Pages serves it (repository root, .nojekyll):
- index.html, 404.html and pypi/index.html are well-formed, declare lang="en" and load nothing from third parties;
- every relative link on those pages, and every sitemap URL, resolves to a file in this repository;
- the JSON-LD block on index.html parses;
- CNAME, .nojekyll, security.txt (Contact, Expires more than 30 days out), robots.txt and pypi/MIRROR.json are sound;
- the package table has unique rows (at least 20) and the marker text the live probe looks for.
"""
import datetime
import html.parser
import json
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = "szlholdings.com"
PAGES = ("index.html", "404.html", "pypi/index.html")
MARKER = "company domain of record"
THIRD_PARTY = re.compile(
    r'<script[^>]+src=|<link[^>]+rel="(?:stylesheet|preconnect|preload|icon)"[^>]+href="https?://|@import\s+url\(https?://'
)


class Strict(html.parser.HTMLParser):
    VOID = {"meta", "link", "br", "img", "input", "hr", "source"}

    def __init__(self, name, errors):
        super().__init__()
        self.name, self.errors = name, errors
        self.stack, self.ids, self.links = [], set(), []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k == "id":
                if v in self.ids:
                    self.errors.append(f"{self.name}: duplicate id {v}")
                self.ids.add(v)
            if k in ("href", "src") and v is not None:
                self.links.append(v)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"{self.name}: unbalanced </{tag}> (open: {self.stack[-3:]})")
        else:
            self.stack.pop()


def resolve_local(root, page_dir, ref):
    """Map a link to the file GitHub Pages would serve from this tree, or None for external links and anchors."""
    parts = urllib.parse.urlsplit(ref)
    if parts.scheme or parts.netloc or not parts.path:  # https:, mailto:, //host, "#frag", "?q"
        return None
    path = urllib.parse.unquote(parts.path)
    target = (root / path.lstrip("/")) if path.startswith("/") else (page_dir / path)
    if path.endswith("/"):
        target = target / "index.html"
    elif target.is_dir():
        target = target / "index.html"  # Pages redirects /dir to /dir/
    return target.resolve()


def check_local_target(root, label, ref, target, errors):
    if root.resolve() not in target.parents:
        errors.append(f"{label}: link {ref!r} leaves the published tree")
    elif not target.is_file():
        errors.append(f"{label}: broken local link {ref!r}")


def check_pages(root, errors):
    links = 0
    for name in PAGES:
        page = root / name
        text = page.read_text(encoding="utf-8")
        p = Strict(name, errors)
        p.feed(text)
        p.close()
        if p.stack:
            errors.append(f"{name}: unclosed tags {p.stack}")
        if THIRD_PARTY.search(text):
            errors.append(f"{name}: external script/stylesheet reference (page must make no third-party requests)")
        if 'lang="en"' not in text:
            errors.append(f"{name}: missing lang attribute")
        for ref in p.links:
            target = resolve_local(root, page.parent, ref)
            if target is not None:
                links += 1
                check_local_target(root, name, ref, target, errors)
    return links


def check_index(root, errors):
    index = (root / "index.html").read_text(encoding="utf-8")
    rows = re.findall(r"<tr>\s*<td><a href=\"https://pypi.org/project/([^/\"]+)/\">", index)
    if len(rows) != len(set(rows)):
        errors.append("duplicate package rows")
    if len(rows) < 20:
        errors.append(f"package table has {len(rows)} rows; expected at least 20")
    if MARKER not in index:
        errors.append(f"marker text {MARKER!r} missing (the live probe depends on it)")
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', index, re.S)
    if not blocks:
        errors.append("index.html: JSON-LD Organization block missing")
    for block in blocks:
        try:
            json.loads(block)
        except ValueError as exc:
            errors.append(f"index.html: JSON-LD does not parse ({exc})")
    return rows


def check_domain_files(root, errors):
    cname = (root / "CNAME").read_text(encoding="utf-8").strip()
    if cname != HOST:
        errors.append(f"CNAME is {cname!r}")
    if not (root / ".nojekyll").exists():
        errors.append(".nojekyll missing (needed so .well-known/ is served)")
    sec = (root / ".well-known/security.txt").read_text(encoding="utf-8")
    m = re.search(r"^Expires:\s*(\S+)", sec, re.M)
    if not m:
        errors.append("security.txt: Expires missing")
    else:
        exp = datetime.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
        if exp < datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30):
            errors.append(f"security.txt: Expires {exp.date()} is within 30 days; renew it")
    if "Contact: mailto:stephen@szlholdings.com" not in sec:
        errors.append("security.txt: Contact missing")
    return cname


def check_sitemap(root, errors):
    robots = (root / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: https://{HOST}/sitemap.xml" not in robots:
        errors.append("robots.txt: Sitemap line missing or not on the domain of record")
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", (root / "sitemap.xml").read_text(encoding="utf-8"))
    if not locs:
        errors.append("sitemap.xml: no <loc> entries")
    for loc in locs:
        parts = urllib.parse.urlsplit(loc)
        if parts.scheme != "https" or parts.netloc != HOST:
            errors.append(f"sitemap.xml: {loc} is not an https://{HOST}/ URL")
            continue
        target = resolve_local(root, root, parts.path or "/")
        check_local_target(root, "sitemap.xml", loc, target, errors)
    return locs


def check_mirror(root, errors):
    meta = json.loads((root / "pypi/MIRROR.json").read_text(encoding="utf-8"))
    for rel in meta.get("files", {}):
        if not (root / "pypi" / rel).is_file():
            errors.append(f"pypi/MIRROR.json lists {rel} but pypi/{rel} is missing")
    if not re.fullmatch(r"[0-9a-f]{40}", str(meta.get("source_commit", ""))):
        errors.append("pypi/MIRROR.json: source_commit is not a full git SHA")


def verify(root=ROOT):
    """Return (errors, summary) for the tree at root."""
    errors = []
    links = check_pages(root, errors)
    rows = check_index(root, errors)
    cname = check_domain_files(root, errors)
    locs = check_sitemap(root, errors)
    check_mirror(root, errors)
    summary = (f"OK {'/'.join(PAGES)} well-formed, no third-party requests, {links} local links resolve, "
               f"CNAME={cname}, security.txt valid, {len(locs)} sitemap URLs resolve, {len(rows)} package rows")
    return errors, summary


def main():
    errors, summary = verify()
    if errors:
        print("\n".join("FAIL " + e for e in errors))
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
