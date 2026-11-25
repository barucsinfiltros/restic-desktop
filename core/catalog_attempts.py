"""Durable, fail-closed record of prototype catalog backup attempts."""

import sqlite3
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path


class UnresolvedAttempt(Exception):
    pass


@contextmanager
def operation_lock(catalog_path):
    """Lock one catalog across cooperating processes; the lock file is persistent."""
    path = Path(str(Path(catalog_path).resolve()) + ".operations.lock")
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        if __import__("os").name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise UnresolvedAttempt("Another catalog process is operating.") from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise UnresolvedAttempt("Another catalog process is operating.") from exc
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _connect(path):
    connection = sqlite3.connect(str(path), timeout=5)
    connection.execute("PRAGMA synchronous = FULL")
    if connection.execute("PRAGMA synchronous").fetchone()[0] != 2:
        connection.close()
        raise sqlite3.OperationalError("FULL synchronization unavailable")
    return connection


def begin(path, profile_id, repository_id):
    """Commit the attempt before starting any Restic process."""
    with closing(_connect(path)) as connection, connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS catalog_backup_attempts (
            id INTEGER PRIMARY KEY, profile_id TEXT NOT NULL, repository_id TEXT NOT NULL,
            started_at TEXT NOT NULL, finished_at TEXT, outcome TEXT NOT NULL,
            snapshot_id TEXT)""")
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM catalog_backup_attempts WHERE outcome = 'running' LIMIT 1"
        ).fetchone():
            raise UnresolvedAttempt("A previous attempt has an unknown outcome; recovery is required.")
        cursor = connection.execute(
            "INSERT INTO catalog_backup_attempts (profile_id, repository_id, started_at, outcome) "
            "VALUES (?, ?, ?, 'running')",
            (str(profile_id), str(repository_id), datetime.now(timezone.utc).isoformat()),
        )
        return cursor.lastrowid


def finish(path, attempt_id, outcome, snapshot_id=None):
    with closing(_connect(path)) as connection, connection:
        cursor = connection.execute(
            "UPDATE catalog_backup_attempts SET outcome=?, finished_at=?, snapshot_id=? "
            "WHERE id=? AND outcome='running'",
            (outcome, datetime.now(timezone.utc).isoformat(), snapshot_id, attempt_id),
        )
        if cursor.rowcount != 1:
            raise UnresolvedAttempt("Attempt state changed unexpectedly.")


def require_no_unresolved_for_catalog(catalog_path):
    """Fail closed if the catalog's standard history contains an unfinished attempt."""
    path = Path(catalog_path).with_suffix(".history.db")
    if not path.exists():
        return
    try:
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
            if connection.execute(
                "SELECT 1 FROM catalog_backup_attempts WHERE outcome='running' LIMIT 1"
            ).fetchone():
                raise UnresolvedAttempt("An attempt has an unknown result.")
    except sqlite3.Error as exc:
        raise UnresolvedAttempt("Attempt history cannot be verified.") from exc
