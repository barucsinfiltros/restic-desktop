"""Integration checks for the manual coordinator using disposable Restic repositories."""

import json
import os
import sqlite3
import subprocess
import sys
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from core.catalog_credentials import WindowsCredentialStore
from core.catalog_domain import CatalogStorageError, LocationSpec
from core.catalog_manual import ManualBackupCoordinator, ManualBackupError
from core.catalog_service import CatalogService
from core.restic_supervisor import Outcome

RESTIC = Path(__file__).resolve().parent.parent / "restic" / "windows" / "restic.exe"


@unittest.skipUnless(sys.platform == "win32" and RESTIC.is_file(), "Requires bundled Windows Restic")
class TemporaryManualBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "keep.txt").write_text("synthetic-content", encoding="utf-8")
        (self.source / "excluded.tmp").write_text("excluded", encoding="utf-8")
        self.repository = self.root / "repository"
        self.password = "temporary-credential-for-tests"
        self.environment = {k: v for k, v in os.environ.items() if not k.upper().startswith("RESTIC_")}
        self.environment["RESTIC_PASSWORD"] = self.password
        self._restic("init")
        config = json.loads(self._restic("cat", "config"))
        self.catalog = CatalogService.create(self.root / "catalog.db")
        self.reference = uuid4()
        self.vault = WindowsCredentialStore()
        self.vault.store(self.reference, self.password)
        self.addCleanup(self.vault.delete, self.reference)
        self.repo = self.catalog.create_repository(
            "temporary", location=LocationSpec(
                "local", str(self.repository), credential_ref=self.reference,
                verified_restic_id=config["id"],
            ), expected_revision=0,
        )
        self.profile = self.catalog.create_profile(
            "temporary", options={"paths": [str(self.source)], "exclude_patterns": ["*.tmp"]},
            repository_ids=[self.repo], expected_revision=1,
        )
        self.catalog.activate_profile(self.profile, expected_revision=2)
        self.history = self.root / "history.db"
        self.coordinator = ManualBackupCoordinator(self.catalog, self.vault, RESTIC, self.history)

    def _restic(self, *args):
        result = subprocess.run(
            [str(RESTIC), "-r", str(self.repository), *args],
            env=self.environment, capture_output=True, timeout=60,
        )
        if result.returncode:
            raise RuntimeError("Synthetic Restic command failed.")
        return result.stdout

    def test_gate_remains_closed_without_test_override(self):
        with self.assertRaises(CatalogStorageError):
            self.coordinator.run(self.profile, self.repo)
        self.assertFalse(self.history.exists())

    def test_manual_backup_with_uuid_tag_exclusion_and_history(self):
        # The override is limited to a disposable catalog and repository in this test.
        with patch.object(self.catalog, "require_operations_allowed"):
            result = self.coordinator.run(self.profile, self.repo)
        self.assertEqual(result.outcome, Outcome.COMPLETED)
        self.assertIsNotNone(result.snapshot_id)
        snapshots = json.loads(self._restic("snapshots", "--json"))
        self.assertEqual(len(snapshots), 1)
        self.assertIn("profile:" + str(self.profile), snapshots[0]["tags"])
        listing = self._restic("ls", result.snapshot_id).decode("utf-8")
        self.assertIn("keep.txt", listing)
        self.assertNotIn("excluded.tmp", listing)
        with closing(sqlite3.connect(self.history)) as connection:
            row = connection.execute(
                "SELECT job_name, repo_name, outcome, snapshot_short_id FROM job_runs"
            ).fetchone()
        self.assertEqual(row, (str(self.profile), str(self.repo), "completed", result.snapshot_id))

    def test_wrong_identity_and_duplicate_lock_prevent_backup(self):
        with self.catalog._storage.transaction(write=True) as (connection, _):
            connection.execute("UPDATE repository_locations SET verified_restic_id = ?",
                               ("b" * 64,))
        with patch.object(self.catalog, "require_operations_allowed"):
            with self.assertRaises(ManualBackupError):
                self.coordinator.run(self.profile, self.repo)
            self.assertTrue(self.coordinator._operation_lock.acquire(blocking=False))
            try:
                with self.assertRaises(ManualBackupError):
                    self.coordinator.run(self.profile, self.repo)
            finally:
                self.coordinator._operation_lock.release()
        self.assertEqual(json.loads(self._restic("snapshots", "--json")), [])

    def test_attempt_exists_before_process_and_compression_off_is_passed(self):
        from core import restic_supervisor
        original = restic_supervisor.start
        calls = []

        def start(request):
            with closing(sqlite3.connect(self.history)) as connection:
                self.assertEqual(connection.execute(
                    "SELECT outcome FROM catalog_backup_attempts"
                ).fetchone()[0], "running")
            calls.append(request.arguments)
            return original(request)

        snapshot = self.catalog.snapshot()
        profile = snapshot.profiles[0]
        self.catalog.update_profile(
            self.profile, profile.display_name, {**profile.options, "compression": "off"},
            expected_revision=snapshot.revision,
        )
        with patch.object(self.catalog, "require_operations_allowed"), \
             patch("core.catalog_manual.restic_supervisor.start", side_effect=start):
            result = self.coordinator.run(self.profile, self.repo)
        self.assertEqual(result.outcome, Outcome.COMPLETED)
        self.assertIn("--compression", calls[-1])
        self.assertEqual(calls[-1][calls[-1].index("--compression") + 1], "off")
        with closing(sqlite3.connect(self.history)) as connection:
            self.assertEqual(connection.execute(
                "SELECT outcome, snapshot_id FROM catalog_backup_attempts"
            ).fetchone(), ("completed", result.snapshot_id))

    def test_unknown_backup_result_remains_running_and_blocks_retry(self):
        original = self.coordinator._wait
        def interrupted(request, progress):
            if request.validate_backup:
                raise RuntimeError("synthetic observation failure")
            return original(request, progress)
        with patch.object(self.catalog, "require_operations_allowed"), \
             patch.object(self.coordinator, "_wait", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                self.coordinator.run(self.profile, self.repo)
            with self.assertRaises(ManualBackupError):
                self.coordinator.run(self.profile, self.repo)
        with closing(sqlite3.connect(self.history)) as connection:
            self.assertEqual(connection.execute(
                "SELECT outcome, finished_at FROM catalog_backup_attempts"
            ).fetchone(), ("running", None))

    def test_partial_snapshot_is_retained_without_success(self):
        from datetime import datetime, timezone
        from core.restic_supervisor import ExecutionResult
        original = self.coordinator._wait
        def incomplete(request, progress):
            if not request.validate_backup:
                return original(request, progress)
            return ExecutionResult("test", None, None, datetime.now(timezone.utc), 1,
                                   Outcome.INCOMPLETE, 3, snapshot_id="a" * 64)
        with patch.object(self.catalog, "require_operations_allowed"), \
             patch.object(self.coordinator, "_wait", side_effect=incomplete):
            result = self.coordinator.run(self.profile, self.repo)
        self.assertFalse(result.succeeded)
        with closing(sqlite3.connect(self.history)) as connection:
            self.assertEqual(connection.execute(
                "SELECT outcome, snapshot_id FROM catalog_backup_attempts"
            ).fetchone(), ("incomplete", "a" * 64))

    def test_catalog_mutation_is_blocked_by_other_instance_operation(self):
        from core.catalog_attempts import operation_lock
        other = CatalogService(self.catalog._storage.path)
        revision = self.catalog.snapshot().revision
        with operation_lock(self.catalog._storage.path):
            with self.assertRaises(CatalogStorageError):
                other.rename_profile(self.profile, "changed", expected_revision=revision)
        self.assertEqual(self.catalog.snapshot().revision, revision)

    def test_verify_existing_temporary_repository_and_reject_identity_change(self):
        from core.catalog_verification import verify_repository
        from core.catalog_domain import InvalidCatalogChange
        with self.catalog._storage.transaction(write=True) as (connection, _):
            connection.execute("UPDATE repository_locations SET verified_restic_id=NULL")
        with patch.object(self.catalog, "require_operations_allowed"):
            observed = verify_repository(self.catalog, self.vault, RESTIC, self.repo)
            location = self.catalog.snapshot().locations[0].spec
            self.assertEqual(location.verified_restic_id, observed)
            with self.catalog._storage.transaction(write=True) as (connection, _):
                connection.execute("UPDATE repository_locations SET verified_restic_id=?", ("b" * 64,))
            with self.assertRaises(InvalidCatalogChange):
                verify_repository(self.catalog, self.vault, RESTIC, self.repo)


if __name__ == "__main__":
    unittest.main()
