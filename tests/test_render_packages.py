"""tools/render_packages.py: the committed table matches the mirrored manifest, and rendering is honest."""
import datetime
import json
import re
import unittest

from sitecopy import SiteCopyTestCase

MANIFEST = "pypi/pypi-packages.v1.json"


class RenderPackagesTest(SiteCopyTestCase):
    def manifest(self):
        return json.loads(self.read(MANIFEST))

    def save_manifest(self, m):
        self.write(MANIFEST, json.dumps(m, indent=2) + "\n")

    def table_rows(self):
        return re.findall(r'<td><a href="https://pypi.org/project/([^/"]+)/">[^<]*</a></td>\s*'
                          r'<td class="num">([^<]*)</td>', self.read("index.html"))

    def test_committed_table_matches_mirrored_manifest(self):
        r = self.run_tool("render_packages.py", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("index.html unchanged", r.stdout)
        published = sorted(p["name"] for p in self.manifest()["packages"] if p.get("status") == "published")
        self.assertEqual([name for name, _ in self.table_rows()], published)

    def test_rerendering_unchanged_data_keeps_the_page_byte_identical(self):
        # Regression: the tool used to stamp today's date as the PyPI read date on every run.
        before = self.read("index.html")
        r = self.run_tool("render_packages.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read("index.html"), before)

    def test_read_date_comes_from_manifest_generated_at_not_today(self):
        m = self.manifest()
        m["generated_at"] = "2026-01-02T03:04:05Z"
        self.save_manifest(m)
        r = self.run_tool("render_packages.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        page = self.read("index.html")
        self.assertIn("read from the PyPI JSON and Simple APIs on 2026-01-02", page)
        self.assertNotIn(f"Simple APIs on {datetime.date.today().isoformat()}", page)
        self.assertIn("read date 2026-01-02 (manifest generated_at)", r.stdout)

    def test_check_reports_drift_without_writing(self):
        m = self.manifest()
        pkg = next(p for p in m["packages"] if p.get("status") == "published")
        pkg["pypi_version"] = "99.0.0"
        self.save_manifest(m)
        before = self.read("index.html")
        r = self.run_tool("render_packages.py", "--check")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("DRIFT", r.stdout)
        self.assertEqual(self.read("index.html"), before)

    def test_render_lists_only_published_sorted_and_queued_sentence(self):
        m = self.manifest()
        m["packages"].append({"name": "aaa-new", "repo": "aaa-new", "status": "published", "pypi_version": "1.2.3",
                              "pypi_url": "https://pypi.org/project/aaa-new/",
                              "source": "https://github.com/szl-holdings/aaa-new"})
        m["packages"].append({"name": "zzz-held", "repo": "zzz-held", "status": "hold",
                              "source": "https://github.com/szl-holdings/zzz-held"})
        m["packages"].append({"name": "b-queued", "repo": "b-queued", "status": "queued",
                              "source": "https://github.com/szl-holdings/b-queued"})
        self.save_manifest(m)
        r = self.run_tool("render_packages.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = self.table_rows()
        names = [name for name, _ in rows]
        self.assertEqual(names, sorted(names))
        self.assertIn(("aaa-new", "1.2.3"), rows)
        self.assertNotIn("zzz-held", names)
        queued = re.search(r"Queued for first release through the same path: (.*?)\.</p>", self.read("index.html"), re.S)
        self.assertIsNotNone(queued)
        self.assertIn("b-queued", queued.group(1).split(", "))
        self.assertNotIn("b-queued", names)
        verify = self.run_tool("verify_site.py")
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_manifest_values_are_html_escaped(self):
        m = self.manifest()
        pkg = next(p for p in m["packages"] if p.get("status") == "published")
        pkg["pypi_version"] = '1.0<script>alert("x")</script>'
        self.save_manifest(m)
        r = self.run_tool("render_packages.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        page = self.read("index.html")
        self.assertNotIn("<script>alert", page)
        self.assertIn("1.0&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", page)

    def test_missing_marker_fails_loudly_instead_of_silently_skipping(self):
        self.edit("index.html", "<!-- packages:end -->", "")
        before = self.read("index.html")
        r = self.run_tool("render_packages.py")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("expected exactly one packages:start/packages:end block, found 0", r.stderr)
        self.assertEqual(self.read("index.html"), before)

    def test_manifest_without_generated_at_is_refused(self):
        m = self.manifest()
        del m["generated_at"]
        self.save_manifest(m)
        r = self.run_tool("render_packages.py", "--check")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("manifest has no generated_at", r.stderr)

    def test_plain_http_manifest_refused_before_any_request(self):
        r = self.run_tool("render_packages.py", "--manifest", "http://example.invalid/pypi-packages.v1.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusing to read the manifest over plain HTTP", r.stderr)


if __name__ == "__main__":
    unittest.main()
