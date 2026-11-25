"""Repository inspection for the staged catalog; the activation gate remains closed."""

import json
from pathlib import Path

from .catalog_domain import RepositoryState
from .catalog_manual import ManualBackupCoordinator, ManualBackupError
from .catalog_attempts import operation_lock, require_no_unresolved_for_catalog
from .restic_supervisor import ExecutionRequest


def verify_repository(catalog, vault, executable, repository_id):
    catalog.require_operations_allowed()
    snapshot = catalog.snapshot()
    repo = next((r for r in snapshot.repositories if r.repository_id == repository_id), None)
    location = next((r.spec for r in snapshot.locations if r.repository_id == repository_id), None)
    if (repo is None or repo.state != RepositoryState.REGISTERED or location is None
            or location.backend not in ("local", "unc") or not location.credential_ref
            or not Path(location.locator).is_dir()):
        raise ManualBackupError("Destination is unavailable or lacks credentials.")
    try:
        password = vault.retrieve(location.credential_ref)
    except Exception:
        raise ManualBackupError("Destination credential is unavailable.") from None
    # Use the same supervised wait and interprocess exclusion as manual backups.
    with operation_lock(catalog._storage.path):
        require_no_unresolved_for_catalog(catalog._storage.path)
        result = ManualBackupCoordinator(catalog, vault, executable, "")._wait(
            ExecutionRequest(str(executable), ("-r", location.locator, "cat", "config"),
                             environment={"RESTIC_PASSWORD": password}, timeout=60), None)
        try:
            identity = json.loads(result.stdout).get("id")
        except (ValueError, AttributeError):
            identity = None
        if not result.succeeded or result.output_truncated or not isinstance(identity, str):
            raise ManualBackupError("Destination identity could not be verified.")
    # The revision prevents saving the observation if the catalog changed in between.
    catalog.record_repository_identity(repository_id, identity, expected_revision=snapshot.revision)
    return identity
