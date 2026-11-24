"""Manual backup prototype. The catalog admission gate remains closed."""

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from . import history_db, restic_supervisor
from .catalog_domain import ProfileState, RepositoryState, require_uuid


class ManualBackupError(Exception):
    """The manual backup could not be admitted or prepared."""


class ManualBackupHistoryError(ManualBackupError):
    """A finished backup could not be recorded. The observed result is retained."""

    def __init__(self, result):
        super().__init__("Backup finished but its history could not be recorded.")
        self.result = result


class ManualBackupCoordinator:
    """Serialize prototype backups in this process; real activation is blocked."""

    _operation_lock = Lock()

    def __init__(self, catalog, vault, executable, history_path):
        self.catalog = catalog
        self.vault = vault
        self.executable = str(executable)
        self.history_path = str(history_path)

    def _wait(self, request, on_progress):
        handle = restic_supervisor.start(request)
        while True:
            result = handle.wait(0.1)
            for event in handle.drain_progress():
                if on_progress is not None:
                    try:
                        on_progress(event)
                    except Exception:
                        # The child must remain supervised even if the UI disappears.
                        pass
            if result is not None:
                return result

    def _history(self, profile_id, repository_id, started, result=None):
        try:
            history_db.insert_job_run(
                job_name=str(profile_id), repo_name=str(repository_id),
                started_at=started.isoformat(),
                finished_at=(result.finished_at.isoformat() if result else None),
                duration_sec=result.duration_seconds if result else None,
                success=result.succeeded if result else False,
                exit_code=result.exit_code if result else None,
                source="catalog_manual",
                error_summary=result.detail if result else "Destination validation failed.",
                snapshot_short_id=result.snapshot_id if result else None,
                outcome=result.outcome.value if result else "failed",
                stop_reason=(result.stop_reason.value if result and result.stop_reason else None),
                db_path=self.history_path,
            )
        except Exception as exc:
            if result is not None:
                raise ManualBackupHistoryError(result) from exc
            raise ManualBackupError("Destination failure could not be recorded.") from exc

    def run(self, profile_id, repository_id, *, on_progress=None):
        """Run one association only after the production admission gate opens."""
        require_uuid(profile_id)
        require_uuid(repository_id)
        self.catalog.require_operations_allowed()
        if not self._operation_lock.acquire(blocking=False):
            raise ManualBackupError("Another catalog operation is in progress.")
        started = datetime.now(timezone.utc)
        try:
            snapshot = self.catalog.snapshot()
            profile = next((p for p in snapshot.profiles if p.profile_id == profile_id), None)
            repo = next((r for r in snapshot.repositories if r.repository_id == repository_id), None)
            location = next((loc.spec for loc in snapshot.locations if loc.repository_id == repository_id), None)
            association = any(link.profile_id == profile_id and link.repository_id == repository_id
                              for link in snapshot.associations)
            if (
                profile is None or profile.state != ProfileState.ACTIVE
                or repo is None or repo.state != RepositoryState.REGISTERED
                or not association or location is None or location.backend not in ("local", "unc")
                or not location.verified_restic_id or not location.credential_ref
                or not Path(location.locator).is_dir()
                or len(profile.options.get("paths", [])) != 1
                or not Path(profile.options["paths"][0]).is_dir()
            ):
                self._history(profile_id, repository_id, started)
                raise ManualBackupError("Profile or destination is unavailable or unverified.")
            try:
                password = self.vault.retrieve(location.credential_ref)
            except Exception:
                self._history(profile_id, repository_id, started)
                raise ManualBackupError("Destination credential is unavailable.") from None

            environment = {"RESTIC_PASSWORD": password}
            probe = self._wait(restic_supervisor.ExecutionRequest(
                self.executable, ("-r", location.locator, "cat", "config"),
                environment=environment, timeout=60,
            ), None)
            try:
                observed_id = json.loads(probe.stdout).get("id")
            except (ValueError, AttributeError):
                observed_id = None
            if not probe.succeeded or probe.output_truncated or observed_id != location.verified_restic_id:
                self._history(profile_id, repository_id, started)
                raise ManualBackupError("Destination identity could not be verified.")
            if self.catalog.snapshot().revision != snapshot.revision:
                self._history(profile_id, repository_id, started)
                raise ManualBackupError("Catalog changed during destination validation.")

            args = ["-r", location.locator, "backup", "--json", "--tag", f"profile:{profile_id}"]
            for pattern in profile.options.get("exclude_patterns", []):
                args.extend(("--exclude", pattern))
            if profile.options.get("exclude_caches"):
                args.append("--exclude-caches")
            if profile.options.get("one_file_system"):
                args.append("--one-file-system")
            if profile.options.get("exclude_if_present"):
                args.extend(("--exclude-if-present", profile.options["exclude_if_present"]))
            if profile.options.get("pack_size"):
                args.extend(("--pack-size", str(profile.options["pack_size"])))
            if profile.options.get("compression") in ("auto", "max"):
                args.extend(("--compression", profile.options["compression"]))
            if profile.options.get("no_cache"):
                args.append("--no-cache")
            if profile.options.get("ignore_inode"):
                args.append("--ignore-inode")
            for tag in profile.options.get("tags", []):
                args.extend(("--tag", tag))
            args.extend(("--", profile.options["paths"][0]))
            result = self._wait(restic_supervisor.ExecutionRequest(
                self.executable, tuple(args), environment=environment,
                timeout=profile.options.get("timeout") or None, validate_backup=True,
                profile_ref=str(profile_id), repository_ref=str(repository_id),
            ), on_progress)
            self._history(profile_id, repository_id, started, result)
            return result
        finally:
            self._operation_lock.release()
