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
        self.assertTrue(r.stdout.startswith("OK index.html/404.html/pypi/index.html/investors/index.html/developers/index.html well-formed"), r.stdout)
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

    def test_mirror_rejects_tampered_canonical_source(self):
        path = self.site / "pypi" / "canonical" / "gen_publish_workflow.py"
        path.write_bytes(path.read_bytes() + b"\n# modified after approval\n")
        self.assert_fails(
            "pypi/MIRROR.json: source_sha256 mismatch for canonical/gen_publish_workflow.py"
        )

    def test_mirror_refuses_missing_digest_coverage(self):
        import json

        path = self.site / "pypi" / "MIRROR.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.pop("source_sha256", None)
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assert_fails(
            "pypi/MIRROR.json: source_sha256 must cover exactly copied sources"
        )

    def test_public_onboarding_distinguishes_evidence_states(self):
        home = self.read("index.html")
        investor = self.read("investors/index.html")
        developer = self.read("developers/index.html")
        self.assertIn('href="/investors/"', home)
        self.assertIn('href="/developers/"', home)
        self.assertIn("HTTP 402 alone is insufficient", investor)
        self.assertIn("No revenue, users, model-quality uplift", investor)
        for header in ("PAYMENT-REQUIRED", "PAYMENT-SIGNATURE", "PAYMENT-RESPONSE"):
            self.assertIn(header, developer)

    def test_investor_broken_local_link_rejected(self):
        self.edit("investors/index.html", 'href="/developers/"', 'href="/not-a-page/"')
        self.assert_fails("investors/index.html: broken local link '/not-a-page/'")

    def test_developer_external_script_rejected(self):
        self.edit("developers/index.html", "</head>", '<script src="https://cdn.example.com/a.js"></script></head>')
        self.assert_fails("developers/index.html: external script/stylesheet reference")

    def test_developer_unbalanced_markup_rejected(self):
        self.edit("developers/index.html", "</main>", "")
        self.assert_fails("developers/index.html: unbalanced </body>")


if __name__ == "__main__":
    unittest.main()
