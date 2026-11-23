import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.catalog_import import InvalidLegacyConfiguration, analyze_bytes, analyze_file


def encode(value):
    return json.dumps(value).encode("utf-8")


class ImportPlanTests(unittest.TestCase):
    def test_legacy_single_and_multi_repository_relations(self):
        data = {
            "repositories": [
                {"name": "first", "type": "local", "path": "/backups/a"},
                {"name": "second", "type": "local", "path": "/backups/b"},
            ],
            "backup_jobs": [
                {"name": "old", "repository": "first", "paths": ["/data"]},
                {"name": "new", "repositories": ["second", "first"]},
            ],
        }
        plan = analyze_bytes(encode(data))
        self.assertEqual([(r.profile_key, r.repository_key, r.position) for r in plan.relationships], [
            ("backup_jobs[0]", "repositories[0]", 0),
            ("backup_jobs[1]", "repositories[1]", 0),
            ("backup_jobs[1]", "repositories[0]", 1),
        ])
        self.assertEqual(plan.conflicts, ())

    def test_missing_duplicates_and_incompatible_references(self):
        plan = analyze_bytes(encode({
            "repositories": [{"name": "dup", "path": "/a"}, {"name": "dup", "path": "/b"}],
            "backup_jobs": [
                {"name": "same", "repository": "dup"},
                {"name": "same", "repository": "missing"},
                {"name": "three", "repositories": ["dup", "dup"]},
                {"name": "four", "repository": "a", "repositories": ["b"]},
                {"name": "five"},
            ],
        }))
        codes = [item.code for item in plan.conflicts]
        self.assertEqual(codes.count("duplicate_name"), 4)
        self.assertEqual(codes.count("missing_or_ambiguous_repository"), 2)
        self.assertIn("duplicate_repository_reference", codes)
        self.assertIn("conflicting_repository_fields", codes)
        self.assertIn("missing_repository", codes)
        self.assertEqual(plan.relationships, ())

    def test_no_secrets_or_arbitrary_input_in_plan_or_error(self):
        secret = "secret-example-521"
        plan = analyze_bytes(encode({
            "rclone_conf_encrypted": secret,
            "repositories": [{
                "name": secret, "type": "https", "path": "https://user:password@example/a",
                "password": secret, "object_secret": secret, secret: {"token": secret},
            }],
            "backup_jobs": [{"name": secret, "repository": secret, "schedule": {"token": secret},
                              "pack_size": "bad", "unknown": secret}],
        }))
        self.assertNotIn(secret, repr(plan))
        self.assertNotIn("password@example", repr(plan))
        categories = {field.category for record in (*plan.repositories, *plan.profiles) for field in record.fields}
        self.assertTrue({"sensitive", "unknown", "incompatible", "not_representable"} <= categories)
        self.assertIn("location_requires_review", [item.code for item in plan.conflicts])
        with self.assertRaises(InvalidLegacyConfiguration) as error:
            analyze_bytes(('{ "' + secret + '": 1, "' + secret + '": 2}').encode())
        self.assertNotIn(secret, str(error.exception))

    def test_canonical_hash_is_stable_and_record_hash_preserves_values(self):
        first = b'{"backup_jobs":[{"name":"a","unknown":1.000}],"repositories":[]}'
        second = b'{ "repositories": [], "backup_jobs": [ {"unknown":1e0, "name":"a"} ] }'
        a, b = analyze_bytes(first), analyze_bytes(second)
        self.assertEqual(a.source_sha256, hashlib.sha256(first).hexdigest())
        self.assertNotEqual(a.source_sha256, b.source_sha256)
        self.assertEqual(a.canonical_sha256, b.canonical_sha256)
        self.assertEqual(a.profiles[0].fingerprint, b.profiles[0].fingerprint)
        c = analyze_bytes(first.replace(b"1.000", b"1.001"))
        self.assertNotEqual(a.canonical_sha256, c.canonical_sha256)
        self.assertNotEqual(a.profiles[0].fingerprint, c.profiles[0].fingerprint)
        self.assertEqual(a.canonical_version, 1)

    def test_unicode_numeric_and_array_canonicalization(self):
        self.assertEqual(analyze_bytes(b'{"n":-0.00}').canonical_sha256,
                         analyze_bytes(b'{"n":0e999}').canonical_sha256)
        self.assertNotEqual(analyze_bytes(b'{"v":[1,2]}').canonical_sha256,
                            analyze_bytes(b'{"v":[2,1]}').canonical_sha256)
        self.assertNotEqual(analyze_bytes('{"v":"é"}'.encode()).canonical_sha256,
                            analyze_bytes('{"v":"e\\u0301"}'.encode()).canonical_sha256)

    def test_reject_invalid_input_without_source_content(self):
        for value in (b"\\xff", b"{", b'{"x":1,"x":2}', b'{"x":NaN}',
                      b'{"x":Infinity}', b'{"x":"\\ud800"}', b'[]',
                      b'{"backup_jobs":{}}', b'{"repositories":[null]}'):
            with self.subTest(value=value), self.assertRaises(InvalidLegacyConfiguration):
                analyze_bytes(value)

    def test_source_file_unchanged_and_no_new_files(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            source = b'{"repositories":[],"backup_jobs":[]}'
            path.write_bytes(source)
            plan = analyze_file(path)
            self.assertEqual(plan.source_sha256, hashlib.sha256(source).hexdigest())
            self.assertEqual(path.read_bytes(), source)
            self.assertEqual([item.name for item in Path(directory).iterdir()], ["settings.json"])


if __name__ == "__main__":
    unittest.main()
