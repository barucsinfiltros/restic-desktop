"""Public domain service for an explicitly opened, staged SQLite catalog.

The global revision supplied by the caller covers every entity and association in
the reviewed snapshot. A command either commits at that revision or changes nothing.
"""

import json
from contextlib import contextmanager
from uuid import UUID, uuid4

from .catalog_domain import (
    CatalogSnapshot,
    CatalogStorageError,
    InvalidCatalogChange,
    LocationSpec,
    Profile,
    ProfileRepository,
    ProfileState,
    Repository,
    RepositoryDraft,
    RepositoryLocation,
    RepositoryState,
    StaleCatalogRevision,
    encode_location,
    encode_profile_options,
    require_text,
    require_uuid,
)
from .catalog_storage import _CatalogStorage


class CatalogService:
    def __init__(self, path):
        self._storage = _CatalogStorage(path)
        with self._storage.transaction() as (connection, _):
            self._storage.validate_lineage(connection)

    @classmethod
    def create(cls, path, *, installation_id: UUID | None = None):
        """Initialize a new staged catalog at an explicit, previously unused path."""
        installation = str(uuid4()) if installation_id is None else require_uuid(installation_id)
        _CatalogStorage(path).initialize(installation)
        return cls(path)

    def snapshot(self) -> CatalogSnapshot:
        """Read entities, locations, and ordered associations at the same revision."""
        with self._storage.transaction() as (connection, state):
            profiles = tuple(
                Profile(
                    UUID(row["profile_id"]), row["display_name"], ProfileState(row["state"]),
                    row["revision"], json.loads(row["options_json"]),
                )
                for row in connection.execute("SELECT * FROM profiles ORDER BY profile_id")
            )
            repositories = tuple(
                Repository(
                    UUID(row["repository_id"]), row["display_name"], RepositoryState(row["state"]),
                    UUID(row["exclusive_profile_id"]) if row["exclusive_profile_id"] else None,
                    row["revision"],
                )
                for row in connection.execute("SELECT * FROM repositories ORDER BY repository_id")
            )
            locations = tuple(
                RepositoryLocation(
                    UUID(row["repository_id"]),
                    LocationSpec(
                        backend=row["backend"],
                        locator=row["locator"],
                        backend_config=json.loads(row["backend_config_json"]),
                        credential_ref=UUID(row["credential_ref"]) if row["credential_ref"] else None,
                        verified_restic_id=row["verified_restic_id"],
                    ),
                    row["location_fingerprint"],
                )
                for row in connection.execute("SELECT * FROM repository_locations ORDER BY repository_id")
            )
            associations = tuple(
                ProfileRepository(UUID(row["profile_id"]), UUID(row["repository_id"]), row["position"])
                for row in connection.execute(
                    "SELECT * FROM profile_repositories ORDER BY profile_id, position"
                )
            )
            return CatalogSnapshot(
                UUID(state["installation_id"]), state["catalog_revision"],
                profiles, repositories, locations, associations,
            )

    @contextmanager
    def _mutation(self, expected_revision):
        if type(expected_revision) is not int or expected_revision < 0:
            raise InvalidCatalogChange("A non-negative catalog revision is required.")
        with self._storage.transaction(write=True) as (connection, state):
            if state["catalog_revision"] != expected_revision:
                raise StaleCatalogRevision("The catalog revision has changed.")
            yield connection
            connection.execute("UPDATE catalog_state SET catalog_revision = catalog_revision + 1")
            # Deferred foreign keys check the final owner link at commit in the storage layer.

    def create_profile(self, display_name, *, expected_revision, options=None,
                       exclusive_repository: RepositoryDraft | None = None) -> UUID:
        name = require_text(display_name, "Profile name")
        encoded = encode_profile_options({} if options is None else options)
        profile_id = uuid4()
        with self._mutation(expected_revision) as connection:
            connection.execute(
                "INSERT INTO profiles (profile_id, display_name, state, options_json) VALUES (?, ?, 'draft', ?)",
                (str(profile_id), name, encoded),
            )
            if exclusive_repository is not None:
                self._insert_repository(connection, exclusive_repository, str(profile_id))
        return profile_id

    def create_repository(self, display_name, *, expected_revision, location=None,
                          state=RepositoryState.REGISTERED, exclusive_profile_id=None) -> UUID:
        owner = require_uuid(exclusive_profile_id) if exclusive_profile_id is not None else None
        with self._mutation(expected_revision) as connection:
            if owner is not None:
                self._editable_profile(connection, owner)
            repository_id = self._insert_repository(
                connection, RepositoryDraft(display_name, location, state), owner
            )
            if owner is not None:
                self._touch(connection, profiles=(owner,))
        return repository_id

    def _insert_repository(self, connection, draft, owner):
        if not isinstance(draft, RepositoryDraft):
            raise InvalidCatalogChange("A repository draft is required.")
        name = require_text(draft.display_name, "Repository name")
        if not isinstance(draft.state, RepositoryState) or draft.state == RepositoryState.UNREGISTERED:
            raise InvalidCatalogChange("A new repository must be registered or pending initialization.")
        if draft.state == RepositoryState.PENDING_INIT and draft.location is None:
            raise InvalidCatalogChange("A pending repository requires a location.")
        repository_id = uuid4()
        key = str(repository_id)
        connection.execute(
            """INSERT INTO repositories (repository_id, display_name, state, exclusive_profile_id)
               VALUES (?, ?, ?, ?)""",
            (key, name, draft.state.value, owner),
        )
        if draft.location is not None:
            self._insert_location(connection, key, encode_location(draft.location))
        if owner is not None:
            self._append_link(connection, owner, key)
        return repository_id

    def register_location(self, repository_id, location: LocationSpec, *, expected_revision):
        """Record the first location without inspecting or initializing its destination."""
        key = require_uuid(repository_id)
        encoded = encode_location(location)
        with self._mutation(expected_revision) as connection:
            self._registered_or_pending(connection, key)
            if connection.execute(
                "SELECT 1 FROM repository_locations WHERE repository_id = ?", (key,)
            ).fetchone():
                raise InvalidCatalogChange("This repository already has a location.")
            self._insert_location(connection, key, encoded)
            self._touch(connection, profiles=self._linked_profiles(connection, key), repositories=(key,))

    @staticmethod
    def _insert_location(connection, key, encoded):
        connection.execute(
            """INSERT INTO repository_locations
               (repository_id, backend, locator, location_fingerprint, verified_restic_id,
                backend_config_json, credential_ref) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (key, *encoded),
        )

    def rename_profile(self, profile_id, display_name, *, expected_revision):
        key = require_uuid(profile_id)
        name = require_text(display_name, "Profile name")
        with self._mutation(expected_revision) as connection:
            self._editable_profile(connection, key)
            connection.execute("UPDATE profiles SET display_name = ? WHERE profile_id = ?", (name, key))
            self._touch(connection, profiles=(key,))

    def rename_repository(self, repository_id, display_name, *, expected_revision):
        key = require_uuid(repository_id)
        name = require_text(display_name, "Repository name")
        with self._mutation(expected_revision) as connection:
            self._repository(connection, key)
            connection.execute(
                "UPDATE repositories SET display_name = ? WHERE repository_id = ?", (name, key)
            )
            self._touch(connection, repositories=(key,))

    def associate_repository(self, profile_id, repository_id, *, expected_revision):
        profile, repository = require_uuid(profile_id), require_uuid(repository_id)
        with self._mutation(expected_revision) as connection:
            self._editable_profile(connection, profile)
            row = self._registered_or_pending(connection, repository)
            if row["exclusive_profile_id"] not in (None, profile):
                raise InvalidCatalogChange("The repository is exclusive to another profile.")
            if profile in self._linked_profiles(connection, repository):
                raise InvalidCatalogChange("The profile is already associated with this repository.")
            self._append_link(connection, profile, repository)
            self._touch(connection, profiles=(profile,), repositories=(repository,))

    def make_exclusive(self, repository_id, owner_id, *, expected_revision, approved_removals=()):
        """Require the exact set of reviewed profile links that will be removed."""
        repository, owner = require_uuid(repository_id), require_uuid(owner_id)
        approved = tuple(require_uuid(profile) for profile in approved_removals)
        with self._mutation(expected_revision) as connection:
            self._editable_profile(connection, owner)
            if self._repository(connection, repository)["exclusive_profile_id"] is not None:
                raise InvalidCatalogChange("Only a shared repository can become exclusive.")
            linked = self._linked_profiles(connection, repository)
            removals = linked - {owner}
            if len(approved) != len(removals) or set(approved) != removals:
                raise InvalidCatalogChange("Approve exactly the affected profiles before removing links.")
            for profile in removals:
                self._remove_link(connection, profile, repository)
                self._draft_if_no_staged_destination(connection, profile)
            self._set_owner(connection, repository, owner)
            if owner not in linked:
                self._append_link(connection, owner, repository)
            self._touch(connection, profiles=linked | {owner}, repositories=(repository,))

    def make_shared(self, repository_id, *, expected_revision):
        repository = require_uuid(repository_id)
        with self._mutation(expected_revision) as connection:
            owner = self._repository(connection, repository)["exclusive_profile_id"]
            if owner is None:
                raise InvalidCatalogChange("The repository is already shared.")
            self._set_owner(connection, repository, None)
            self._touch(connection, profiles=(owner,), repositories=(repository,))

    def transfer_exclusive(self, repository_id, new_owner_id, *, approved_owner_id, expected_revision):
        """Transfer ownership after approval of the old owner's removal at the reviewed revision."""
        repository = require_uuid(repository_id)
        new_owner, previous_owner = require_uuid(new_owner_id), require_uuid(approved_owner_id)
        with self._mutation(expected_revision) as connection:
            self._editable_profile(connection, new_owner)
            owner = self._repository(connection, repository)["exclusive_profile_id"]
            if owner != previous_owner or owner == new_owner:
                raise InvalidCatalogChange("The approved owner does not match a valid transfer.")
            self._remove_link(connection, owner, repository)
            self._set_owner(connection, repository, new_owner)
            self._append_link(connection, new_owner, repository)
            self._draft_if_no_staged_destination(connection, owner)
            self._touch(connection, profiles=(owner, new_owner), repositories=(repository,))

    def reorder_associations(self, profile_id, repository_ids, *, expected_revision):
        profile = require_uuid(profile_id)
        ordered = tuple(require_uuid(repository) for repository in repository_ids)
        with self._mutation(expected_revision) as connection:
            self._editable_profile(connection, profile)
            positions = dict(connection.execute(
                "SELECT repository_id, position FROM profile_repositories WHERE profile_id = ?",
                (profile,),
            ))
            if len(ordered) != len(positions) or set(ordered) != positions.keys():
                raise InvalidCatalogChange("The new order must contain every existing association once.")
            # Reinsert within the transaction: the owner-link FK is deferred, and no
            # immediate uniqueness constraint sees a temporary duplicate position.
            connection.execute("DELETE FROM profile_repositories WHERE profile_id = ?", (profile,))
            connection.executemany(
                "INSERT INTO profile_repositories (profile_id, repository_id, position) VALUES (?, ?, ?)",
                ((profile, repository, position) for position, repository in enumerate(ordered)),
            )
            self._touch(
                connection, profiles=(profile,),
                repositories=(repository for i, repository in enumerate(ordered) if positions[repository] != i),
            )

    def activate_profile(self, profile_id, *, expected_revision):
        """Mark a draft active from staged metadata, without checking credentials or launching Restic."""
        profile = require_uuid(profile_id)
        with self._mutation(expected_revision) as connection:
            if self._editable_profile(connection, profile)["state"] != ProfileState.DRAFT.value:
                raise InvalidCatalogChange("Only a draft profile can be marked active.")
            if not self._has_staged_destination(connection, profile):
                raise InvalidCatalogChange("An active profile requires a registered and verified destination.")
            connection.execute("UPDATE profiles SET state = 'active' WHERE profile_id = ?", (profile,))
            self._touch(connection, profiles=(profile,))

    def archive_profile(self, profile_id, *, expected_revision):
        profile = require_uuid(profile_id)
        with self._mutation(expected_revision) as connection:
            self._editable_profile(connection, profile)
            connection.execute("UPDATE profiles SET state = 'archived' WHERE profile_id = ?", (profile,))
            exclusive = (
                row[0] for row in connection.execute(
                    "SELECT repository_id FROM repositories WHERE exclusive_profile_id = ?", (profile,)
                )
            )
            self._touch(connection, profiles=(profile,), repositories=exclusive)

    def unregister_repository(self, repository_id, *, expected_revision):
        repository = require_uuid(repository_id)
        with self._mutation(expected_revision) as connection:
            self._registered_or_pending(connection, repository)
            connection.execute(
                "UPDATE repositories SET state = 'unregistered' WHERE repository_id = ?", (repository,)
            )
            self._touch(
                connection, profiles=self._linked_profiles(connection, repository), repositories=(repository,)
            )

    @staticmethod
    def _editable_profile(connection, profile):
        row = connection.execute("SELECT * FROM profiles WHERE profile_id = ?", (profile,)).fetchone()
        if row is None or row["state"] == ProfileState.ARCHIVED.value:
            raise InvalidCatalogChange("A non-archived profile is required.")
        return row

    @staticmethod
    def _repository(connection, repository):
        row = connection.execute(
            "SELECT * FROM repositories WHERE repository_id = ?", (repository,)
        ).fetchone()
        if row is None:
            raise InvalidCatalogChange("The repository does not exist.")
        return row

    def _registered_or_pending(self, connection, repository):
        row = self._repository(connection, repository)
        if row["state"] == RepositoryState.UNREGISTERED.value:
            raise InvalidCatalogChange("The repository is unregistered.")
        return row

    @staticmethod
    def _linked_profiles(connection, repository):
        return {
            row[0] for row in connection.execute(
                "SELECT profile_id FROM profile_repositories WHERE repository_id = ?", (repository,)
            )
        }

    @staticmethod
    def _append_link(connection, profile, repository):
        connection.execute(
            """INSERT INTO profile_repositories (profile_id, repository_id, position)
               SELECT ?, ?, COALESCE(MAX(position) + 1, 0)
               FROM profile_repositories WHERE profile_id = ?""",
            (profile, repository, profile),
        )

    @staticmethod
    def _remove_link(connection, profile, repository):
        connection.execute(
            "DELETE FROM profile_repositories WHERE profile_id = ? AND repository_id = ?",
            (profile, repository),
        )

    @staticmethod
    def _set_owner(connection, repository, owner):
        connection.execute(
            "UPDATE repositories SET exclusive_profile_id = ? WHERE repository_id = ?", (owner, repository)
        )

    @staticmethod
    def _has_staged_destination(connection, profile):
        return connection.execute(
            """SELECT 1 FROM profile_repositories AS association
               JOIN repositories AS repo USING (repository_id)
               JOIN repository_locations AS location USING (repository_id)
               WHERE association.profile_id = ? AND repo.state = 'registered'
                 AND location.verified_restic_id IS NOT NULL LIMIT 1""",
            (profile,),
        ).fetchone() is not None

    def _draft_if_no_staged_destination(self, connection, profile):
        if not self._has_staged_destination(connection, profile):
            connection.execute(
                "UPDATE profiles SET state = 'draft' WHERE profile_id = ? AND state = 'active'",
                (profile,),
            )

    @staticmethod
    def _touch(connection, *, profiles=(), repositories=()):
        connection.executemany(
            "UPDATE profiles SET revision = revision + 1 WHERE profile_id = ?",
            ((profile,) for profile in profiles),
        )
        connection.executemany(
            "UPDATE repositories SET revision = revision + 1 WHERE repository_id = ?",
            ((repository,) for repository in repositories),
        )
