import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from contextlib import closing
from tempfile import TemporaryDirectory
from uuid import uuid4

from core import catalog_attempts
from core.catalog_domain import InvalidCatalogChange, encode_profile_options


class AttemptTests(unittest.TestCase):
    def test_reserved_tag_and_safe_tags(self):
        for tag in ("profile:abc", " PROFILE:abc"):
            with self.subTest(tag=tag), self.assertRaises(InvalidCatalogChange):
                encode_profile_options({"tags": [tag]})
        encode_profile_options({"tags": ["myprofile:abc", "ordinary"]})

    def test_attempt_is_durable_and_unknown_outcome_blocks_retry(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "history.db"
            attempt = catalog_attempts.begin(path, uuid4(), uuid4())
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute(
                    "SELECT outcome, finished_at FROM catalog_backup_attempts"
                ).fetchone(), ("running", None))
            with self.assertRaises(catalog_attempts.UnresolvedAttempt):
                catalog_attempts.begin(path, uuid4(), uuid4())
            catalog_attempts.finish(path, attempt, "failed")
            self.assertTrue(catalog_attempts.begin(path, uuid4(), uuid4()))

    def test_lock_excludes_another_process(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "catalog.db"
            script = ("from core.catalog_attempts import operation_lock; "
                      "import sys; "
                      "cm=operation_lock(sys.argv[1]); cm.__enter__()")
            with catalog_attempts.operation_lock(path):
                child = subprocess.run([sys.executable, "-B", "-c", script, str(path)],
                                       capture_output=True, timeout=15)
            self.assertNotEqual(child.returncode, 0)
            child = subprocess.run([sys.executable, "-B", "-c", script, str(path)],
                                   capture_output=True, timeout=15)
            self.assertEqual(child.returncode, 0, child.stderr.decode(errors="replace"))
