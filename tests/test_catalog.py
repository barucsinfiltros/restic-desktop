"""Staged catalog tests. Every database and simulated destination is disposable."""

import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from core.catalog_domain import (
    CatalogStorageError,
    InvalidCatalogChange,
    LocationSpec,
    ProfileState,
    RepositoryDraft,
    RepositoryState,
    StaleCatalogRevision,
)
from core.catalog_service import CatalogService
from core.catalog_storage import _CatalogStorage


class CatalogFixture(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "catalog.db"
        self.installation = uuid4()
        self.service = CatalogService.create(self.database, installation_id=self.installation)
        self.location = LocationSpec("local", str(self.root / "repo"), verified_restic_id="a" * 64)

    def change(self, command, *args, **kwargs):
        if command == self.service.create_profile and "options" not in kwargs:
            kwargs["options"] = {"paths": [str(self.root / "source")]}
        return command(*args, **kwargs, expected_revision=self.service.snapshot().revision)

    def profile(self, name="Profile"):
        return self.change(self.service.create_profile, name)

    def repository(self, name="Repository", **kwargs):
        return self.change(self.service.create_repository, name, **kwargs)

    def link(self, profile, repository):
        self.change(self.service.associate_repository, profile, repository)

    def raw(self):
        connection = sqlite3.connect(self.database, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        return closing(connection)

    def profile_row(self, profile):
        return next(item for item in self.service.snapshot().profiles if item.profile_id == profile)

    def repository_row(self, repository):
        return next(item for item in self.service.snapshot().repositories if item.repository_id == repository)


class CatalogServiceTests(CatalogFixture):
    def test_create_reopen_and_rename_keep_independent_ids(self):
        first = self.change(self.service.create_profile, "Same", options={"paths": [str(self.root / "source")], "tags": ["tag"]})
        second = self.profile("Same")
        repo = self.repository("Same")
        ref = uuid4()
        location = LocationSpec("local", self.location.locator, credential_ref=ref)
        self.change(self.service.register_location, repo, location)
        self.change(self.service.rename_profile, first, "New profile name")
        self.change(self.service.rename_repository, repo, "New repository name")
        snapshot = CatalogService(self.database).snapshot()
        self.assertEqual(snapshot.installation_id, self.installation)
        self.assertEqual(snapshot.revision, 6)
        self.assertNotEqual(first, second)
        self.assertEqual({p.profile_id for p in snapshot.profiles}, {first, second})
        self.assertEqual(self.profile_row(first).options, {"paths": [str(self.root / "source")], "tags": ["tag"]})
        self.assertEqual(self.profile_row(first).display_name, "New profile name")
        self.assertEqual(self.repository_row(repo).display_name, "New repository name")
        self.assertEqual(self.repository_row(repo).revision, 3)
        self.assertEqual(snapshot.locations[0].spec.credential_ref, ref)
        self.assertFalse(Path(location.locator).exists())

    def test_create_exclusive_with_profile_reserves_pending_destination_atomically(self):
        profile = self.change(
            self.service.create_profile, "Owner",
            exclusive_repository=RepositoryDraft("Exclusive", self.location, RepositoryState.PENDING_INIT),
        )
        snapshot = self.service.snapshot()
        exclusive, = snapshot.repositories
        link, = snapshot.associations
        self.assertEqual(snapshot.revision, 1)
        self.assertEqual(exclusive.exclusive_profile_id, profile)
        self.assertEqual(exclusive.state, RepositoryState.PENDING_INIT)
        self.assertEqual((link.profile_id, link.repository_id, link.position), (profile, exclusive.repository_id, 0))
        self.assertEqual(snapshot.locations[0].repository_id, exclusive.repository_id)
        self.assertEqual(self.profile_row(profile).state, ProfileState.DRAFT)
        self.assertFalse(Path(self.location.locator).exists())
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.activate_profile, profile)
        with self.assertRaises(InvalidCatalogChange):
            self.change(
                self.service.create_profile, "Invalid",
                exclusive_repository=RepositoryDraft("Missing location", state=RepositoryState.PENDING_INIT),
            )
        self.assertEqual(self.service.snapshot(), snapshot)

    def test_shared_repository_accepts_multiple_profiles_and_rejects_duplicate_link(self):
        first, second = self.profile(), self.profile()
        repo = self.repository()
        self.link(first, repo)
        self.link(second, repo)
        snapshot = self.service.snapshot()
        self.assertEqual({link.profile_id for link in snapshot.associations}, {first, second})
        self.assertEqual([link.position for link in snapshot.associations], [0, 0])
        self.assertIsNone(self.repository_row(repo).exclusive_profile_id)
        with self.assertRaises(InvalidCatalogChange):
            self.link(first, repo)
        self.assertEqual(self.service.snapshot(), snapshot)

    def test_exclusive_rejects_non_owner_and_can_be_shared_without_moving_owner(self):
        owner, other = self.profile(), self.profile()
        previous = self.repository()
        self.link(owner, previous)
        exclusive = self.repository(exclusive_profile_id=owner)
        before = self.service.snapshot()
        with self.assertRaises(InvalidCatalogChange):
            self.link(other, exclusive)
        self.assertEqual(self.service.snapshot(), before)
        self.change(self.service.make_shared, exclusive)
        after = self.service.snapshot()
        self.assertEqual(after.associations, before.associations)
        self.assertEqual(self.repository_row(exclusive).repository_id, exclusive)
        self.assertIsNone(self.repository_row(exclusive).exclusive_profile_id)
        self.link(other, exclusive)

    def test_make_exclusive_requires_exact_removal_approval_and_preserves_owner_order(self):
        owner, losing, remaining = self.profile(), self.profile(), self.profile()
        prior = self.repository()
        converted = self.repository(location=self.location)
        alternate = self.repository(location=self.location)
        self.link(owner, prior)
        for profile in (owner, losing, remaining):
            self.link(profile, converted)
        self.link(remaining, alternate)
        for profile in (losing, remaining):
            self.change(self.service.activate_profile, profile)
        before = self.service.snapshot()
        for approval in ((), (losing,), (losing, remaining, owner), (losing, losing)):
            with self.subTest(approval=approval), self.assertRaises(InvalidCatalogChange):
                self.change(self.service.make_exclusive, converted, owner, approved_removals=approval)
        self.assertEqual(self.service.snapshot(), before)
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.make_exclusive, converted, owner, approved_removals=(losing, remaining))
        self.assertEqual(self.service.snapshot(), before)
        self.change(self.service.dissociate_repository, losing, converted)
        self.change(self.service.dissociate_repository, remaining, converted)
        self.change(self.service.make_exclusive, converted, owner)
        result = self.service.snapshot()
        self.assertEqual(result.revision, before.revision + 3)
        self.assertEqual(self.repository_row(converted).exclusive_profile_id, owner)
        links = [link for link in result.associations if link.repository_id == converted]
        self.assertEqual([(link.profile_id, link.position) for link in links], [(owner, 1)])
        self.assertEqual(self.profile_row(losing).state, ProfileState.DRAFT)
        self.assertEqual(self.profile_row(remaining).state, ProfileState.ACTIVE)

    def test_shared_repository_can_become_exclusive_with_a_new_link(self):
        owner = self.profile()
        repo = self.repository()
        self.change(self.service.make_exclusive, repo, owner)
        self.assertEqual(self.repository_row(repo).exclusive_profile_id, owner)
        link, = self.service.snapshot().associations
        self.assertEqual((link.profile_id, link.position), (owner, 0))

    def test_transfer_requires_review_and_preserves_other_relationships(self):
        old_owner, new_owner = self.profile(), self.profile()
        exclusive = self.repository(exclusive_profile_id=old_owner, location=self.location)
        other = self.repository()
        self.link(new_owner, other)
        self.change(self.service.activate_profile, old_owner)
        before = self.service.snapshot()
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.transfer_exclusive, exclusive, new_owner, approved_owner_id=new_owner)
        self.assertEqual(self.service.snapshot(), before)
        self.change(self.service.transfer_exclusive, exclusive, new_owner, approved_owner_id=old_owner)
        links = self.service.snapshot().associations
        self.assertEqual([(link.profile_id, link.repository_id, link.position) for link in links], [
            (new_owner, other, 0), (new_owner, exclusive, 1),
        ])
        self.assertEqual(self.repository_row(exclusive).exclusive_profile_id, new_owner)
        self.assertEqual(self.profile_row(old_owner).state, ProfileState.DRAFT)

    def test_reorder_includes_owner_link_and_rejects_incomplete_or_duplicate_order(self):
        owner = self.profile()
        exclusive = self.repository(exclusive_profile_id=owner)
        shared = self.repository()
        self.link(owner, shared)
        before = self.service.snapshot()
        for invalid in ((exclusive,), (exclusive, exclusive), (exclusive, uuid4())):
            with self.subTest(invalid=invalid), self.assertRaises(InvalidCatalogChange):
                self.change(self.service.reorder_associations, owner, invalid)
        self.assertEqual(self.service.snapshot(), before)
        self.change(self.service.reorder_associations, owner, (shared, exclusive))
        self.assertEqual(
            [(link.repository_id, link.position) for link in self.service.snapshot().associations],
            [(shared, 0), (exclusive, 1)],
        )
        self.assertEqual(self.repository_row(exclusive).exclusive_profile_id, owner)

    def test_archive_and_unregister_keep_associations_location_and_physical_data(self):
        path = Path(self.location.locator)
        path.mkdir()
        sentinel = path / "keep"
        sentinel.write_text("data", encoding="utf-8")
        owner, other = self.profile(), self.profile()
        exclusive = self.repository(exclusive_profile_id=owner, location=self.location)
        before = self.service.snapshot()
        self.change(self.service.make_shared, exclusive)
        self.change(self.service.archive_profile, owner)
        self.change(self.service.unregister_repository, exclusive)
        after = self.service.snapshot()
        self.assertEqual(self.profile_row(owner).state, ProfileState.ARCHIVED)
        self.assertEqual(self.repository_row(exclusive).state, RepositoryState.UNREGISTERED)
        self.assertIsNone(self.repository_row(exclusive).exclusive_profile_id)
        self.assertEqual(after.associations, ())
        self.assertEqual(self.profile_row(owner).options, {})
        self.assertEqual(after.locations, before.locations)
        with self.assertRaises(InvalidCatalogChange):
            self.link(other, exclusive)
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.transfer_exclusive, exclusive, owner, approved_owner_id=other)
        self.assertEqual(self.service.snapshot(), after)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "data")

    def test_archive_requires_all_exclusive_repositories_resolved(self):
        owner, new_owner = self.profile(), self.profile()
        first = self.repository(exclusive_profile_id=owner, location=self.location)
        second = self.repository(exclusive_profile_id=owner, location=self.location)
        self.change(self.service.unregister_repository, second)
        before = self.service.snapshot()
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.archive_profile, owner)
        self.assertEqual(self.service.snapshot(), before)

        self.change(self.service.transfer_exclusive, first, new_owner, approved_owner_id=owner)
        before = self.service.snapshot()
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.archive_profile, owner)
        self.assertEqual(self.service.snapshot(), before)

        self.change(self.service.make_shared, second)
        before = self.service.snapshot()
        self.change(self.service.archive_profile, owner)
        after = self.service.snapshot()
        self.assertEqual(after.revision, before.revision + 1)
        self.assertEqual(self.profile_row(owner).state, ProfileState.ARCHIVED)
        self.assertEqual(self.repository_row(first).exclusive_profile_id, new_owner)
        self.assertIsNone(self.repository_row(second).exclusive_profile_id)
        self.assertEqual(
            after.associations,
            tuple(link for link in before.associations if link.profile_id != owner),
        )
        self.assertEqual(self.profile_row(owner).options, {})

    def test_archive_rejects_pending_exclusive_until_made_shared(self):
        owner = self.profile()
        repository = self.repository(
            exclusive_profile_id=owner,
            state=RepositoryState.PENDING_INIT,
            location=self.location,
        )
        before = self.service.snapshot()
        self.assertEqual(self.repository_row(repository).state, RepositoryState.PENDING_INIT)
        self.assertEqual(self.repository_row(repository).exclusive_profile_id, owner)

        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.archive_profile, owner)
        after_rejection = self.service.snapshot()
        self.assertEqual(after_rejection, before)
        self.assertEqual(after_rejection.revision, before.revision)

        self.change(self.service.make_shared, repository)
        before_archive = self.service.snapshot()
        self.change(self.service.archive_profile, owner)
        after_archive = self.service.snapshot()
        self.assertEqual(self.profile_row(owner).state, ProfileState.ARCHIVED)
        self.assertIsNone(self.repository_row(repository).exclusive_profile_id)
        self.assertEqual(self.repository_row(repository).state, RepositoryState.PENDING_INIT)
        self.assertEqual(len(before_archive.associations), 1)
        self.assertEqual(after_archive.associations, ())
        self.assertEqual(self.profile_row(owner).options, {})

    def test_archive_without_exclusive_repositories(self):
        owner = self.profile()
        repository = self.repository()
        self.link(owner, repository)
        before = self.service.snapshot()
        self.change(self.service.archive_profile, owner)
        after = self.service.snapshot()
        self.assertEqual(after.revision, before.revision + 1)
        self.assertEqual(self.profile_row(owner).state, ProfileState.ARCHIVED)
        self.assertEqual(len(before.associations), 1)
        self.assertEqual(after.associations, ())
        self.assertEqual(self.profile_row(owner).options, {})

    def test_archive_rolls_back_association_removal_when_update_fails(self):
        owner = self.profile()
        repository = self.repository()
        self.link(owner, repository)
        before = self.service.snapshot()
        with self.raw() as connection:
            connection.executescript("""
                CREATE TRIGGER reject_archive BEFORE UPDATE OF state ON profiles
                WHEN NEW.state = 'archived'
                BEGIN
                    SELECT RAISE(ABORT, 'injected failure');
                END;
            """)
        with self.assertRaises(CatalogStorageError):
            self.change(self.service.archive_profile, owner)
        self.assertEqual(self.service.snapshot(), before)

    def test_dissociation_rejects_exclusive_and_preserves_catalog(self):
        owner = self.profile()
        repository = self.repository(exclusive_profile_id=owner)
        before = self.service.snapshot()
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.dissociate_repository, owner, repository)
        self.assertEqual(self.service.snapshot(), before)

    def test_open_rejects_incompatible_profiles_without_modifying_catalog(self):
        for options in ("{}", '{"paths":[]}', '{"paths":["one","two"]}', "broken"):
            with self.subTest(options=options):
                profile = self.profile()
                with self.raw() as connection:
                    connection.execute("UPDATE profiles SET options_json = ? WHERE profile_id = ?",
                                       (options, str(profile)))
                before = self.database.read_bytes()
                with self.assertRaises(CatalogStorageError):
                    CatalogService(self.database)
                self.assertEqual(self.database.read_bytes(), before)
                with self.raw() as connection:
                    connection.execute("UPDATE profiles SET options_json = ? WHERE profile_id = ?",
                                       ('{"paths":["valid"]}', str(profile)))

    def test_open_rejects_active_profile_without_registered_verified_destination(self):
        profile = self.profile()
        repository = self.repository(location=self.location)
        self.link(profile, repository)
        self.change(self.service.activate_profile, profile)
        with self.raw() as connection:
            connection.execute("UPDATE repositories SET state = 'unregistered' WHERE repository_id = ?",
                               (str(repository),))
        before = self.database.read_bytes()
        with self.assertRaises(CatalogStorageError):
            CatalogService(self.database)
        self.assertEqual(self.database.read_bytes(), before)
        with self.raw() as connection:
            connection.execute("UPDATE repositories SET state = 'registered' WHERE repository_id = ?",
                               (str(repository),))
            connection.execute("UPDATE repository_locations SET verified_restic_id = NULL WHERE repository_id = ?",
                               (str(repository),))
        before = self.database.read_bytes()
        with self.assertRaises(CatalogStorageError):
            CatalogService(self.database)
        self.assertEqual(self.database.read_bytes(), before)

    def test_open_rejects_archived_profile_with_options_or_association(self):
        profile = self.profile()
        repository = self.repository()
        self.link(profile, repository)
        with self.raw() as connection:
            connection.execute("UPDATE profiles SET state = 'archived' WHERE profile_id = ?",
                               (str(profile),))
        before = self.database.read_bytes()
        with self.assertRaises(CatalogStorageError):
            CatalogService(self.database)
        self.assertEqual(self.database.read_bytes(), before)
        with self.raw() as connection:
            connection.execute("UPDATE profiles SET options_json = '{}' WHERE profile_id = ?",
                               (str(profile),))
        before = self.database.read_bytes()
        with self.assertRaises(CatalogStorageError):
            CatalogService(self.database)
        self.assertEqual(self.database.read_bytes(), before)

    def test_unregister_demotes_only_profiles_without_other_valid_destinations(self):
        losing, remaining = self.profile(), self.profile()
        first = self.repository(location=self.location)
        second = self.repository(location=self.location)
        self.link(losing, first)
        self.link(remaining, first)
        self.link(remaining, second)
        self.change(self.service.activate_profile, losing)
        self.change(self.service.activate_profile, remaining)
        before = self.service.snapshot()
        self.change(self.service.unregister_repository, first)
        after = self.service.snapshot()
        self.assertEqual(after.revision, before.revision + 1)
        self.assertEqual(self.profile_row(losing).state, ProfileState.DRAFT)
        self.assertEqual(self.profile_row(remaining).state, ProfileState.ACTIVE)
        self.assertEqual(after.associations, before.associations)

    def test_backup_is_consistent_and_does_not_overwrite_existing_files(self):
        profile = self.profile()
        repository = self.repository(location=self.location)
        self.link(profile, repository)
        before = self.service.snapshot()
        backup = self.root / "backup.db"
        self.service.backup_to(backup)
        self.assertEqual(CatalogService(backup).snapshot(), before)
        with closing(sqlite3.connect(backup)) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            connection.execute("PRAGMA foreign_keys = ON")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        original = backup.read_bytes()
        with self.assertRaises(CatalogStorageError):
            self.service.backup_to(backup)
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(self.service.snapshot(), before)

    def test_unregister_rolls_back_when_profile_demotion_fails(self):
        profile = self.profile()
        repository = self.repository(location=self.location)
        self.link(profile, repository)
        self.change(self.service.activate_profile, profile)
        before = self.service.snapshot()
        with self.raw() as connection:
            connection.executescript("""
                CREATE TRIGGER reject_demotion BEFORE UPDATE OF state ON profiles
                WHEN NEW.state = 'draft'
                BEGIN
                    SELECT RAISE(ABORT, 'injected failure');
                END;
            """)
        with self.assertRaises(CatalogStorageError):
            self.change(self.service.unregister_repository, repository)
        self.assertEqual(self.service.snapshot(), before)

    def test_staged_catalog_rejects_operational_admission(self):
        before = self.service.snapshot()
        with self.assertRaises(CatalogStorageError):
            self.service.require_operations_allowed()
        self.assertEqual(self.service.snapshot(), before)

    def test_profile_associations_are_saved_atomically(self):
        owner, other = self.profile(), self.profile()
        shared = self.repository()
        exclusive = self.repository(exclusive_profile_id=other)
        before = self.service.snapshot()
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.update_profile, owner, "Changed",
                        {"paths": [str(self.root / "source")]},
                        repository_ids=[shared, exclusive])
        self.assertEqual(self.service.snapshot(), before)
        self.change(self.service.update_profile, owner, "Changed",
                    {"paths": [str(self.root / "source")]}, repository_ids=[shared])
        self.assertEqual(self.profile_row(owner).display_name, "Changed")
        self.assertIn(shared, [link.repository_id for link in self.service.snapshot().associations
                               if link.profile_id == owner])

    def test_profile_requires_one_folder_and_edits_transactionally(self):
        for paths in ([], ["one", "two"]):
            before = self.service.snapshot()
            with self.assertRaises(InvalidCatalogChange):
                self.change(self.service.create_profile, "Invalid", options={"paths": paths})
            self.assertEqual(self.service.snapshot(), before)
        profile = self.profile()
        before = self.service.snapshot()
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.update_profile, profile, "Updated", {"paths": []})
        self.assertEqual(self.service.snapshot(), before)
        self.change(self.service.update_profile, profile, "Updated", {
            "paths": [str(self.root / "new")], "exclude_patterns": ["*.tmp"],
        })
        self.assertEqual(self.profile_row(profile).display_name, "Updated")
        self.assertEqual(self.profile_row(profile).options["exclude_patterns"], ["*.tmp"])
        with self.assertRaises(StaleCatalogRevision):
            self.service.update_profile(profile, "Stale", {"paths": [str(self.root)]},
                                        expected_revision=before.revision)

    def test_rejects_missing_references_archived_owner_and_invalid_options(self):
        archived = self.profile()
        owner = self.profile()
        repo = self.repository()
        self.change(self.service.archive_profile, archived)
        before = self.service.snapshot()
        calls = (
            (self.service.associate_repository, (owner, uuid4()), {}),
            (self.service.associate_repository, (uuid4(), repo), {}),
            (self.service.make_exclusive, (repo, archived), {}),
            (self.service.create_repository, ("Archived owner",), {"exclusive_profile_id": archived}),
            (self.service.create_profile, ("Invalid",), {"options": {"tags": "not a list"}}),
            (self.service.create_profile, ("Secret",), {"options": {"password": "should not persist"}}),
            (self.service.create_profile, ("   ",), {}),
        )
        for command, args, kwargs in calls:
            with self.subTest(command=command.__name__), self.assertRaises(InvalidCatalogChange):
                self.change(command, *args, **kwargs)
        self.assertEqual(self.service.snapshot(), before)

    def test_locations_are_validated_and_fingerprints_are_candidates_only(self):
        first, second = self.repository(), self.repository()
        before = self.service.snapshot()
        invalid = (
            LocationSpec("local", "relative"),
            LocationSpec("rest", "https://user:password@example.test/data"),
            LocationSpec("s3", "https://example.test/bucket?secret=123"),
            LocationSpec("sftp", "sftp://user:password@example.test//srv"),
            LocationSpec("s3", "s3:example.test/bucket", {"secret_access_key": "password"}),
            LocationSpec("local", self.location.locator, credential_ref="opaque string"),
        )
        for location in invalid:
            with self.subTest(backend=location.backend), self.assertRaises(InvalidCatalogChange):
                self.change(self.service.register_location, first, location)
        self.assertEqual(self.service.snapshot(), before)
        safe = LocationSpec("rest", "rest:https://example.test/data")
        self.change(self.service.register_location, first, safe)
        self.change(self.service.register_location, second, safe)
        snapshot = self.service.snapshot()
        self.assertEqual(len(snapshot.locations), 2)
        self.assertEqual(len({location.location_fingerprint for location in snapshot.locations}), 1)
        with self.assertRaises(InvalidCatalogChange):
            self.change(self.service.register_location, first, self.location)
        self.assertEqual(self.service.snapshot(), snapshot)

    def test_supported_repository_locator_forms_round_trip_without_io(self):
        for backend, locator in (
            ("unc", "//server/share/subpath"),
            ("sftp", "sftp:user@example.test:/data"),
            ("sftp", "sftp://user@example.test:2222//data"),
            ("rclone", "rclone:Example Remote:"),
            ("s3", "s3:example.test/bucket/path"),
            ("wasabi", "s3:https://example.test/bucket"),
            ("b2", "b2:bucket"),
            ("azure", "azure:container:/path"),
        ):
            with self.subTest(backend=backend, locator=locator):
                repository = self.repository(location=LocationSpec(backend, locator))
                location = next(item for item in self.service.snapshot().locations
                                if item.repository_id == repository)
                self.assertEqual((location.spec.backend, location.spec.locator), (backend, locator))

    def test_transfer_rolls_back_on_sql_error_after_changing_owner(self):
        old_owner, new_owner = self.profile(), self.profile()
        exclusive = self.repository(exclusive_profile_id=old_owner, location=self.location)
        self.change(self.service.activate_profile, old_owner)
        before = self.service.snapshot()
        with self.raw() as connection:
            connection.executescript("""
                CREATE TRIGGER fail_reassignment BEFORE INSERT ON profile_repositories
                BEGIN
                    SELECT RAISE(ABORT, 'injected failure');
                END;
                """)
        with self.assertRaises(CatalogStorageError):
            self.change(self.service.transfer_exclusive, exclusive, new_owner, approved_owner_id=old_owner)
        self.assertEqual(self.service.snapshot(), before)

    def test_stale_review_cannot_override_newer_link(self):
        old_owner, other = self.profile(), self.profile()
        repo = self.repository()
        self.link(old_owner, repo)
        reviewed = self.service.snapshot().revision
        self.link(other, repo)
        before = self.service.snapshot()
        with self.assertRaises(StaleCatalogRevision):
            self.service.make_exclusive(repo, old_owner, expected_revision=reviewed)
        self.assertEqual(self.service.snapshot(), before)

    def test_concurrent_incompatible_transfers_only_commit_one_review(self):
        owner, first, second = self.profile(), self.profile(), self.profile()
        repo = self.repository(exclusive_profile_id=owner)
        revision = self.service.snapshot().revision
        barrier = threading.Barrier(2, timeout=10)

        def transfer(target):
            service = CatalogService(self.database)
            barrier.wait()
            try:
                service.transfer_exclusive(repo, target, approved_owner_id=owner, expected_revision=revision)
            except (StaleCatalogRevision, CatalogStorageError):
                return None
            return target

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(transfer, (first, second)))
        winner, = [target for target in outcomes if target is not None]
        snapshot = self.service.snapshot()
        self.assertEqual(snapshot.revision, revision + 1)
        self.assertEqual(self.repository_row(repo).exclusive_profile_id, winner)
        self.assertEqual([link.profile_id for link in snapshot.associations], [winner])


class CatalogDDLTests(CatalogFixture):
    def test_every_connection_enables_foreign_keys(self):
        store = _CatalogStorage(self.database)
        for write in (False, True, False, True):
            with store.transaction(write=write) as (connection, _):
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_owner_link_enforced_at_commit_and_survives_delete_rollback(self):
        owner = str(self.profile())
        repository = str(uuid4())
        with self.raw() as connection:
            connection.execute("BEGIN")
            connection.execute(
                "INSERT INTO repositories(repository_id, display_name, state, exclusive_profile_id) "
                "VALUES (?, 'Exclusive', 'pending_init', ?)", (repository, owner),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.commit()
            connection.rollback()
            self.assertEqual(connection.execute("SELECT count(*) FROM repositories").fetchone()[0], 0)
            connection.execute("BEGIN")
            connection.execute(
                "INSERT INTO repositories(repository_id, display_name, state, exclusive_profile_id) "
                "VALUES (?, 'Exclusive', 'pending_init', ?)", (repository, owner),
            )
            connection.execute("INSERT INTO profile_repositories VALUES (?, ?, 0)", (owner, repository))
            connection.commit()
            connection.execute("BEGIN")
            connection.execute("DELETE FROM profile_repositories WHERE repository_id = ?", (repository,))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.commit()
            connection.rollback()
            self.assertEqual(connection.execute("SELECT count(*) FROM profile_repositories").fetchone()[0], 1)

    def test_triggers_enforce_insert_update_and_owner_changes(self):
        owner, other = self.profile(), self.profile()
        exclusive = self.repository(exclusive_profile_id=owner)
        shared = self.repository()
        self.link(other, shared)
        with self.raw() as connection:
            for sql, parameters in (
                ("INSERT INTO profile_repositories VALUES (?, ?, 1)", (other, exclusive)),
                ("UPDATE profile_repositories SET repository_id = ? WHERE repository_id = ?", (exclusive, shared)),
                ("UPDATE repositories SET exclusive_profile_id = ? WHERE repository_id = ?", (owner, shared)),
            ):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(sql, tuple(map(str, parameters)))

    def test_sql_uniqueness_and_reference_checks(self):
        owner = self.profile()
        first, second = self.repository(), self.repository()
        self.link(owner, first)
        with self.raw() as connection:
            for repo, position in ((first, 1), (second, 0), (uuid4(), 1)):
                with self.subTest(repo=repo, position=position), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO profile_repositories VALUES (?, ?, ?)",
                                       (str(owner), str(repo), position))

    def test_lineage_rejects_wrong_entity_duplicate_and_missing_predecessor(self):
        for table, first, second in (
            ("legacy_profiles", self.profile(), self.profile()),
            ("legacy_repositories", self.repository(), self.repository()),
        ):
            with self.subTest(table=table), self.raw() as connection:
                batches = [str(uuid4()) for _ in range(3)]
                connection.executemany(
                    "INSERT INTO legacy_import_batches VALUES (?, 1, 'raw', 'canonical', 0)",
                    ((batch,) for batch in batches),
                )
                self.insert_lineage(connection, table, batches[0], "row:0", first)
                self.insert_lineage(connection, table, batches[1], "row:3", first, batches[0], "row:0")
                for batch, entity, parent in (
                    (batches[1], first, batches[0]), (batches[2], second, batches[0]),
                    (batches[2], first, str(uuid4())),
                ):
                    with self.assertRaises(sqlite3.IntegrityError):
                        self.insert_lineage(connection, table, batch, "row:1", entity, parent, "row:0")
        self.assertEqual(CatalogService(self.database).snapshot(), self.service.snapshot())

    def test_catalog_rejects_existing_cycles_in_each_lineage_table(self):
        for table, entity in (("legacy_profiles", self.profile()), ("legacy_repositories", self.repository())):
            with self.subTest(table=table), self.raw() as connection:
                first, second = str(uuid4()), str(uuid4())
                connection.executemany(
                    "INSERT INTO legacy_import_batches VALUES (?, 1, 'raw', 'canonical', 0)",
                    ((batch,) for batch in (first, second)),
                )
                self.insert_lineage(connection, table, first, "row:0", entity)
                self.insert_lineage(connection, table, second, "row:0", entity, first, "row:0")
                connection.execute(
                    f"UPDATE {table} SET predecessor_batch_id = ?, predecessor_source_key = 'row:0' "
                    "WHERE batch_id = ?", (second, first),
                )
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                with self.assertRaisesRegex(CatalogStorageError, "lineage cycle"):
                    CatalogService(self.database)
                connection.execute(
                    f"UPDATE {table} SET predecessor_batch_id = NULL, predecessor_source_key = NULL "
                    "WHERE batch_id = ?", (first,),
                )

    @staticmethod
    def insert_lineage(connection, table, batch, source, entity, predecessor=None, predecessor_source=None):
        connection.execute(
            f"INSERT INTO {table} VALUES (?, ?, 'Name', 'hash', '{{}}', ?, ?, ?, ?, 'decision')",
            (batch, source, str(entity), predecessor, predecessor_source, "new" if predecessor is None else "managed"),
        )

    def test_never_initializes_existing_database_or_opens_active_catalog(self):
        other = self.root / "existing.db"
        with closing(sqlite3.connect(other)) as connection:
            connection.execute("CREATE TABLE history(value TEXT)")
            connection.execute("INSERT INTO history VALUES ('keep')")
            connection.commit()
        previous = other.read_bytes()
        for action in (CatalogService.create, CatalogService):
            with self.assertRaises(CatalogStorageError):
                action(other)
        self.assertEqual(other.read_bytes(), previous)
        missing = self.root / "missing.db"
        with self.assertRaises(CatalogStorageError):
            CatalogService(missing)
        self.assertFalse(missing.exists())
        with self.raw() as connection:
            connection.execute("UPDATE catalog_state SET mode = 'active'")
        with self.assertRaises(CatalogStorageError):
            CatalogService(self.database)
        with self.assertRaises(CatalogStorageError):
            self.service.create_profile("Should fail", options={"paths": [str(self.root)]}, expected_revision=0)


if __name__ == "__main__":
    unittest.main()
