"""tools/verify_site.py: the committed tree passes, and each class of defect it guards against is caught."""
import datetime
import unittest

from sitecopy import SiteCopyTestCase


class VerifySiteTest(SiteCopyTestCase):
    def assert_fails(self, needle):
        r = self.run_tool("verify_site.py")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(needle, r.stdout)
        return r

    def test_committed_tree_passes(self):
        r = self.run_tool("verify_site.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("OK index.html/404.html/pypi/index.html well-formed"), r.stdout)
        self.assertIn("CNAME=szlholdings.com", r.stdout)

    def test_external_stylesheet_rejected(self):
        self.edit("index.html", "</head>", '<link rel="stylesheet" href="https://cdn.example.com/x.css">\n</head>')
        self.assert_fails("index.html: external script/stylesheet reference")

    def test_external_script_rejected_on_pypi_page(self):
        self.edit("pypi/index.html", "</main>", '<script src="https://cdn.example.com/x.js"></script></main>')
        self.assert_fails("pypi/index.html: external script/stylesheet reference")

    def test_unbalanced_markup_rejected(self):
        self.edit("404.html", "</main>", "")
        self.assert_fails("404.html: unbalanced </body>")

    def test_missing_lang_rejected(self):
        self.edit("404.html", '<html lang="en">', "<html>")
        self.assert_fails("404.html: missing lang attribute")

    def test_broken_local_link_rejected(self):
        self.edit("index.html", 'href="/pypi/release-path.md"', 'href="/pypi/release-path-v9.md"')
        self.assert_fails("index.html: broken local link '/pypi/release-path-v9.md'")

    def test_relative_link_on_pypi_page_resolves_against_its_directory(self):
        (self.site / "pypi" / "canonical" / "publish-pypi.yml").unlink()
        self.assert_fails("pypi/index.html: broken local link 'canonical/publish-pypi.yml'")

    def test_link_escaping_the_tree_rejected(self):
        self.edit("404.html", 'href="/"', 'href="../../etc/passwd"')
        self.assert_fails("404.html: link '../../etc/passwd' leaves the published tree")

    def test_malformed_json_ld_rejected(self):
        self.edit("index.html", '"@type": "Organization",', '"@type": "Organization",,')
        self.assert_fails("index.html: JSON-LD does not parse")

    def test_wrong_cname_rejected(self):
        self.write("CNAME", "www.szlholdings.com\n")
        self.assert_fails("CNAME is 'www.szlholdings.com'")

    def test_missing_nojekyll_rejected(self):
        (self.site / ".nojekyll").unlink()
        self.assert_fails(".nojekyll missing")

    def test_security_txt_expiring_within_30_days_rejected(self):
        soon = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        text = self.read(".well-known/security.txt")
        expires = next(line for line in text.splitlines() if line.startswith("Expires:"))
        self.write(".well-known/security.txt", text.replace(expires, f"Expires: {soon}"))
        self.assert_fails("is within 30 days; renew it")

    def test_security_txt_contact_required(self):
        self.edit(".well-known/security.txt", "Contact: mailto:stephen@szlholdings.com", "Contact: https://example.com")
        self.assert_fails("security.txt: Contact missing")

    def test_sitemap_url_must_resolve(self):
        self.edit("sitemap.xml", "</urlset>", "  <url><loc>https://szlholdings.com/careers/</loc></url>\n</urlset>")
        self.assert_fails("sitemap.xml: broken local link 'https://szlholdings.com/careers/'")

    def test_sitemap_url_must_be_on_domain_of_record(self):
        self.edit("sitemap.xml", "<loc>https://szlholdings.com/</loc>", "<loc>http://szlholdings.com/</loc>")
        self.assert_fails("sitemap.xml: http://szlholdings.com/ is not an https://szlholdings.com/ URL")

    def test_duplicate_package_rows_rejected(self):
        start = "<!-- packages:start -->\n"
        text = self.read("index.html")
        first_row = text[text.index(start) + len(start):text.index("</tr>", text.index(start)) + len("</tr>")]
        self.write("index.html", text.replace(start, start + first_row + "\n", 1))
        self.assert_fails("duplicate package rows")

    def test_marker_text_required_by_live_probe(self):
        text = self.read("index.html")
        self.write("index.html", text.replace("company domain of record", "company homepage"))
        self.assert_fails("marker text 'company domain of record' missing")

    def test_mirror_manifest_files_must_exist(self):
        (self.site / "pypi" / "canonical" / "gen_publish_workflow.py").unlink()
        self.assert_fails("pypi/MIRROR.json lists canonical/gen_publish_workflow.py but pypi/canonical/"
                          "gen_publish_workflow.py is missing")


if __name__ == "__main__":
    unittest.main()
