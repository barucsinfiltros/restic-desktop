"""Private SQLite storage for the standalone staged catalog."""

import os
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path

from .catalog_domain import CatalogStorageError


SCHEMA_VERSION = 1

# DDL from DOCS/PHASE_4_DESIGN.md. The store owns connection and transaction scope.
_SCHEMA = """

CREATE TABLE profiles (
    profile_id TEXT NOT NULL PRIMARY KEY,
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    state TEXT NOT NULL CHECK (state IN ('draft', 'active', 'archived')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    options_json TEXT NOT NULL
);

CREATE TABLE repositories (
    repository_id TEXT NOT NULL PRIMARY KEY,
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    state TEXT NOT NULL CHECK (
        state IN ('pending_init', 'registered', 'unregistered')
    ),
    exclusive_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    FOREIGN KEY (exclusive_profile_id, repository_id)
        REFERENCES profile_repositories(profile_id, repository_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE repository_locations (
    repository_id TEXT NOT NULL PRIMARY KEY
        REFERENCES repositories(repository_id) ON DELETE RESTRICT,
    backend TEXT NOT NULL CHECK (length(trim(backend)) > 0),
    locator TEXT NOT NULL CHECK (length(trim(locator)) > 0),
    location_fingerprint TEXT,
    verified_restic_id TEXT,
    backend_config_json TEXT NOT NULL,
    credential_ref TEXT
);

CREATE TABLE profile_repositories (
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE RESTRICT,
    repository_id TEXT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE RESTRICT,
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (profile_id, repository_id),
    UNIQUE (profile_id, position)
);

CREATE TABLE catalog_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    mode TEXT NOT NULL CHECK (mode IN ('staged', 'active')),
    installation_id TEXT NOT NULL,
    transition_id TEXT,
    catalog_revision INTEGER NOT NULL DEFAULT 0 CHECK (catalog_revision >= 0),
    import_source_fingerprint TEXT
);

CREATE TABLE legacy_import_batches (
    batch_id TEXT NOT NULL PRIMARY KEY,
    canonicalization_version INTEGER NOT NULL CHECK (canonicalization_version > 0),
    source_fingerprint TEXT NOT NULL,
    canonical_fingerprint TEXT NOT NULL,
    base_catalog_revision INTEGER NOT NULL CHECK (base_catalog_revision >= 0)
);

CREATE TABLE legacy_profiles (
    batch_id TEXT NOT NULL REFERENCES legacy_import_batches(batch_id) ON DELETE RESTRICT,
    source_key TEXT NOT NULL,
    legacy_name TEXT NOT NULL,
    record_fingerprint TEXT NOT NULL,
    baseline_json TEXT NOT NULL,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE RESTRICT,
    predecessor_batch_id TEXT,
    predecessor_source_key TEXT,
    link_method TEXT NOT NULL CHECK (link_method IN ('new', 'managed', 'reviewed')),
    decision_ref TEXT NOT NULL,
    PRIMARY KEY (batch_id, source_key),
    UNIQUE (batch_id, profile_id),
    UNIQUE (batch_id, source_key, profile_id),
    CHECK ((predecessor_batch_id IS NULL) = (predecessor_source_key IS NULL)),
    FOREIGN KEY (predecessor_batch_id, predecessor_source_key, profile_id)
        REFERENCES legacy_profiles(batch_id, source_key, profile_id) ON DELETE RESTRICT
);

CREATE TABLE legacy_repositories (
    batch_id TEXT NOT NULL REFERENCES legacy_import_batches(batch_id) ON DELETE RESTRICT,
    source_key TEXT NOT NULL,
    legacy_name TEXT NOT NULL,
    record_fingerprint TEXT NOT NULL,
    baseline_json TEXT NOT NULL,
    repository_id TEXT NOT NULL REFERENCES repositories(repository_id) ON DELETE RESTRICT,
    predecessor_batch_id TEXT,
    predecessor_source_key TEXT,
    link_method TEXT NOT NULL CHECK (link_method IN ('new', 'managed', 'reviewed')),
    decision_ref TEXT NOT NULL,
    PRIMARY KEY (batch_id, source_key),
    UNIQUE (batch_id, repository_id),
    UNIQUE (batch_id, source_key, repository_id),
    CHECK ((predecessor_batch_id IS NULL) = (predecessor_source_key IS NULL)),
    FOREIGN KEY (predecessor_batch_id, predecessor_source_key, repository_id)
        REFERENCES legacy_repositories(batch_id, source_key, repository_id) ON DELETE RESTRICT
);

CREATE TABLE legacy_job_aliases (
    alias TEXT COLLATE BINARY NOT NULL PRIMARY KEY
        CHECK (length(trim(alias)) > 0),
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE RESTRICT
);

CREATE INDEX profiles_listing_idx ON profiles(state, display_name);
CREATE INDEX repositories_listing_idx ON repositories(state, display_name);
CREATE INDEX repositories_owner_idx ON repositories(exclusive_profile_id);
CREATE INDEX locations_lookup_idx ON repository_locations(backend, location_fingerprint);
CREATE INDEX locations_restic_id_idx ON repository_locations(verified_restic_id);
CREATE INDEX profile_repositories_reverse_idx
    ON profile_repositories(repository_id, profile_id);
CREATE INDEX legacy_profiles_name_idx ON legacy_profiles(legacy_name);
CREATE INDEX legacy_repositories_name_idx ON legacy_repositories(legacy_name);
CREATE INDEX legacy_profiles_target_idx ON legacy_profiles(profile_id);
CREATE INDEX legacy_repositories_target_idx ON legacy_repositories(repository_id);
CREATE INDEX legacy_job_aliases_profile_idx ON legacy_job_aliases(profile_id);

CREATE TRIGGER enforce_exclusive_link_insert
BEFORE INSERT ON profile_repositories
WHEN EXISTS (
    SELECT 1 FROM repositories
    WHERE repository_id = NEW.repository_id
      AND exclusive_profile_id IS NOT NULL
      AND exclusive_profile_id <> NEW.profile_id
)
BEGIN
    SELECT RAISE(ABORT, 'exclusive repository belongs to another profile');
END;

CREATE TRIGGER enforce_exclusive_link_update
BEFORE UPDATE OF repository_id, profile_id ON profile_repositories
WHEN EXISTS (
    SELECT 1 FROM repositories
    WHERE repository_id = NEW.repository_id
      AND exclusive_profile_id IS NOT NULL
      AND exclusive_profile_id <> NEW.profile_id
)
BEGIN
    SELECT RAISE(ABORT, 'exclusive repository belongs to another profile');
END;

CREATE TRIGGER enforce_exclusive_owner_update
BEFORE UPDATE OF exclusive_profile_id ON repositories
WHEN NEW.exclusive_profile_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM profile_repositories
    WHERE repository_id = NEW.repository_id
      AND profile_id <> NEW.exclusive_profile_id
)
BEGIN
    SELECT RAISE(ABORT, 'repository has associations with another profile');
END;

PRAGMA user_version = 1;
"""


class _CatalogStorage:
    def __init__(self, path):
        self.path = Path(path).resolve()

    def initialize(self, installation_id):
        # Reserve a new path without ever opening an existing database for initialization.
        try:
            with self.path.open("xb"):
                pass
        except OSError as exc:
            raise CatalogStorageError("Cannot create a new catalog at this path.") from exc

        with self._connection("rw") as connection:
            # executescript is only used here on an empty database with no transaction.
            connection.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA)
            connection.execute(
                "INSERT INTO catalog_state (singleton, mode, installation_id) VALUES (1, 'staged', ?)",
                (installation_id,),
            )
            connection.commit()

    @contextmanager
    def _connection(self, mode):
        try:
            connection = sqlite3.connect(
                f"{self.path.as_uri()}?mode={mode}", uri=True, isolation_level=None
            )
        except sqlite3.Error as exc:
            raise CatalogStorageError("Cannot open the catalog database.") from exc
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise CatalogStorageError("SQLite foreign keys could not be enabled.")
            yield connection
        except sqlite3.Error as exc:
            raise CatalogStorageError("Catalog transaction failed.") from exc
        finally:
            try:
                if connection.in_transaction:
                    connection.rollback()
            finally:
                connection.close()

    @contextmanager
    def transaction(self, *, write=False):
        with self._connection("rw" if write else "ro") as connection:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise CatalogStorageError("Unsupported catalog schema version.")
            state = connection.execute(
                "SELECT * FROM catalog_state WHERE singleton = 1"
            ).fetchone()
            if state is None or state["mode"] != "staged":
                raise CatalogStorageError("Only an initialized staged catalog is supported.")
            yield connection, state
            connection.commit()

    def backup_to(self, destination):
        """Publish a verified SQLite snapshot without replacing an existing file."""
        destination = Path(destination).absolute()
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".restic-catalog-", suffix=".tmp", dir=destination.parent
            )
            os.close(descriptor)
        except OSError as exc:
            raise CatalogStorageError("Cannot prepare the catalog backup.") from exc

        temporary = Path(temporary_name)
        try:
            with self.transaction() as (source, _):
                with closing(sqlite3.connect(temporary, isolation_level=None)) as target:
                    source.backup(target)
                    target.execute("PRAGMA foreign_keys = ON")
                    if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise CatalogStorageError("Catalog backup failed integrity verification.")
                    if target.execute("PRAGMA foreign_key_check").fetchone() is not None:
                        raise CatalogStorageError("Catalog backup has invalid references.")
                    self.validate_lineage(target)
            # Hard-link publication fails atomically when the destination already exists.
            # The temporary file is on the same volume as the requested destination.
            os.link(temporary, destination)
        except (OSError, sqlite3.Error) as exc:
            raise CatalogStorageError("Catalog backup could not be published.") from exc
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def validate_lineage(connection):
        # This block has no lineage writes. When opening a catalog, reject cycles
        # that the approved self-referencing foreign keys alone permit.
        for table in ("legacy_profiles", "legacy_repositories"):
            entity_column = "profile_id" if table == "legacy_profiles" else "repository_id"
            rows = connection.execute(
                f"""SELECT batch_id, source_key, predecessor_batch_id, predecessor_source_key,
                           {entity_column}
                    FROM {table}"""
            )
            links = {
                (batch, source): ((previous_batch, previous_source), entity)
                for batch, source, previous_batch, previous_source, entity in rows
            }
            visited = set()
            for start, (_, entity) in links.items():
                node = start
                chain = set()
                while node != (None, None):
                    if node not in links or links[node][1] != entity:
                        raise CatalogStorageError("Catalog contains invalid lineage predecessors.")
                    if node in visited:
                        break
                    if node in chain:
                        raise CatalogStorageError("Catalog contains a lineage cycle.")
                    chain.add(node)
                    node = links[node][0]
                visited.update(chain)
