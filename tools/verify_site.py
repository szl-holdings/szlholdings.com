#!/usr/bin/env python3
"""Structural checks for the szlholdings.com page. Standard library only; exit 1 on any failure."""
import datetime, html.parser, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
errors = []

class Strict(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.stack = []; self.ids = set()
    VOID = {"meta", "link", "br", "img", "input", "hr", "source"}
    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k == "id":
                if v in self.ids: errors.append(f"duplicate id {v}")
                self.ids.add(v)
        if tag not in self.VOID: self.stack.append(tag)
    def handle_endtag(self, tag):
        if tag in self.VOID: return
        if not self.stack or self.stack[-1] != tag: errors.append(f"unbalanced </{tag}> (open: {self.stack[-3:]})")
        else: self.stack.pop()

for name in ("index.html", "404.html"):
    text = (ROOT / name).read_text(encoding="utf-8")
    p = Strict(); p.feed(text)
    if p.stack: errors.append(f"{name}: unclosed tags {p.stack}")
    if re.search(r'<script[^>]+src=|<link[^>]+rel="(?:stylesheet|preconnect|preload|icon)"[^>]+href="https?://|@import\s+url\(https?://', text):
        errors.append(f"{name}: external script/stylesheet reference (page must make no third-party requests)")
    if 'lang="en"' not in text: errors.append(f"{name}: missing lang attribute")

cname = (ROOT / "CNAME").read_text().strip()
if cname != "szlholdings.com": errors.append(f"CNAME is {cname!r}")
if not (ROOT / ".nojekyll").exists(): errors.append(".nojekyll missing (needed so .well-known/ is served)")
sec = (ROOT / ".well-known/security.txt").read_text()
m = re.search(r"^Expires:\s*(\S+)", sec, re.M)
if not m: errors.append("security.txt: Expires missing")
else:
    exp = datetime.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
    if exp < datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30):
        errors.append(f"security.txt: Expires {exp.date()} is within 30 days; renew it")
if "Contact: mailto:stephen@szlholdings.com" not in sec: errors.append("security.txt: Contact missing")
index = (ROOT / "index.html").read_text()
rows = re.findall(r"<tr>\s*<td><a href=\"https://pypi.org/project/([^/\"]+)/\">", index)
if len(rows) != len(set(rows)): errors.append("duplicate package rows")
if len(rows) < 20: errors.append(f"package table has {len(rows)} rows; expected at least 20")
if "company domain of record" not in index: errors.append("marker text 'company domain of record' missing (the live probe depends on it)")

if errors:
    print("\n".join("FAIL " + e for e in errors)); sys.exit(1)
print(f"OK index.html/404.html well-formed, no third-party requests, CNAME={cname}, security.txt valid, {len(rows)} package rows")
