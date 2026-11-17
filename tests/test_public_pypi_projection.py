"""The private PyPI governance index must never leak unpublished identities to Pages."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from public_pypi_projection import ProjectionHold, public_projection

SHA = "a" * 40
PUBLIC = {
    "name": "szl-public",
    "repo": "szl-public",
    "status": "published",
    "pypi_version": "1.2.0",
    "pypi_url": "https://pypi.org/project/szl-public/",
    "source": "https://github.com/szl-holdings/szl-public",
}
PRIVATE = {
    "name": "confidential-laboratory-asset",
    "repo": "private-repo",
    "status": "hold",
    "reason": "confidential research: do not distribute",
}

class PublicProjectionTest(unittest.TestCase):
    def source(self):
        return {"schema": "szl.pypi-packages.v1", "generated_at": "2026-11-16T11:55:00Z",
                "packages": [PUBLIC.copy(), PRIVATE.copy(), {"name": "unreleased-candidate", "status": "queued"}]}

    def render(self, source):
        return public_projection(json.dumps(source).encode("utf-8"), SHA)

    def test_published_only_no_private_or_queued_fields(self):
        body = self.render(self.source())
        text = body.decode("utf-8")
        output = json.loads(text)
        self.assertEqual(output["counts"], {"published": 1, "queued": 0})
        self.assertEqual(output["packages"], [PUBLIC])
        for forbidden in ("confidential-laboratory-asset", "private-repo",
                          "unreleased-candidate", "confidential research"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(output["public_projection"]["source_commit"], SHA)
        self.assertEqual(len(output["public_projection"]["source_manifest_sha256"]), 64)

    def test_deterministic_sorted_published_order(self):
        m = self.source()
        extra = dict(PUBLIC, name="a-new-package", repo="a-new-package",
                     pypi_url="https://pypi.org/project/a-new-package/",
                     source="https://github.com/szl-holdings/a-new-package")
        m["packages"].append(extra)
        a = self.render(m)
        self.assertEqual(a, self.render(m))
        self.assertEqual([x["name"] for x in json.loads(a)["packages"]],
                         ["a-new-package", "szl-public"])

    def test_rejects_bad_sha(self):
        with self.assertRaises(ProjectionHold):
            public_projection(json.dumps(self.source()).encode(), "main")

    def test_rejects_bad_timestamps(self):
        for value in ("", "2026-11-16T11:55:00", "2026-11-16T11:55:00-05:00"):
            m = self.source()
            m["generated_at"] = value
            with self.subTest(value=value), self.assertRaises(ProjectionHold):
                self.render(m)

    def test_rejects_wrong_source_and_pypi_urls(self):
        for key, bad in (("source", "https://github.com/other/szl-public"),
                         ("pypi_url", "https://bad.example/project/szl-public/"),
                         ("name", "../unsafe"), ("pypi_version", "1.0<script>")):
            m = self.source()
            m["packages"][0][key] = bad
            with self.subTest(key=key), self.assertRaises(ProjectionHold):
                self.render(m)

    def test_rejects_duplicate_published_names(self):
        m = self.source()
        m["packages"].append(PUBLIC.copy())
        with self.assertRaisesRegex(ProjectionHold, "DUPLICATE_PUBLISHED_NAME"):
            self.render(m)

    def test_rejects_empty_publication(self):
        m = self.source()
        m["packages"] = [PRIVATE]
        with self.assertRaises(ProjectionHold):
            self.render(m)

    def test_rejects_duplicate_json_keys(self):
        with self.assertRaises(ProjectionHold):
            public_projection(b'{"schema":"a","schema":"b"}', SHA)

    def test_rejects_oversized_source(self):
        with self.assertRaises(ProjectionHold):
            public_projection(b" " * 2_000_001, SHA)

if __name__ == "__main__":
    unittest.main()
