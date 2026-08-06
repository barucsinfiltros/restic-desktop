"""
SQLite history store for job runs, repo stats samples, and dashboard cache.

File lives beside restic_settings.json (CWD / settings path). Stdlib sqlite3 only.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = 1
DEFAULT_DB_NAME = "restic_history.db"
CACHE_KEY = "latest"


def history_db_path(settings_filename: str = "restic_settings.json") -> str:
    """Resolve restic_history.db next to the settings file."""
    settings_path = os.path.abspath(settings_filename)
    return os.path.join(os.path.dirname(settings_path), DEFAULT_DB_NAME)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def format_duration(seconds: Optional[float]) -> str:
    """Format duration as HH:MM:SS, or — if missing."""
    if seconds is None:
        return "—"
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return "—"
    if total < 0:
        total = 0
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@contextmanager
def _connect(db_path: Optional[str] = None):
    path = db_path or history_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def migrate(db_path: Optional[str] = None) -> None:
    """Create tables / bump schema_version if needed."""
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS job_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                duration_sec REAL,
                success INTEGER NOT NULL,
                exit_code INTEGER,
                source TEXT NOT NULL,
                error_summary TEXT,
                snapshot_short_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_job_runs_job_finished
                ON job_runs (job_name, finished_at DESC);

            CREATE INDEX IF NOT EXISTS idx_job_runs_repo_finished
                ON job_runs (repo_name, finished_at DESC);

            CREATE TABLE IF NOT EXISTS repo_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT NOT NULL,
                sampled_at TEXT NOT NULL,
                total_size INTEGER,
                snapshot_count INTEGER,
                last_backup_at TEXT,
                last_snapshot_short_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_repo_stats_name_sampled
                ON repo_stats (repo_name, sampled_at DESC);

            CREATE TABLE IF NOT EXISTS dashboard_cache (
                cache_key TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
        else:
            try:
                current = int(row["value"])
            except (TypeError, ValueError):
                current = 0
            if current < SCHEMA_VERSION:
                conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                    (str(SCHEMA_VERSION),),
                )


def insert_job_run(
    *,
    job_name: str,
    repo_name: str,
    started_at: str,
    finished_at: Optional[str] = None,
    duration_sec: Optional[float] = None,
    success: bool,
    exit_code: Optional[int] = None,
    source: str = "gui",
    error_summary: Optional[str] = None,
    snapshot_short_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Insert one job_runs row. Returns row id."""
    migrate(db_path)
    finished = finished_at or _utc_now_iso()
    summary = (error_summary or "").strip()
    if len(summary) > 500:
        summary = summary[:497] + "..."
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO job_runs (
                job_name, repo_name, started_at, finished_at, duration_sec,
                success, exit_code, source, error_summary, snapshot_short_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_name,
                repo_name,
                started_at,
                finished,
                duration_sec,
                1 if success else 0,
                exit_code,
                source,
                summary or None,
                snapshot_short_id or None,
            ),
        )
        return int(cur.lastrowid)


def get_latest_job_run(
    job_name: str, db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Return the most recent job_runs row for a job name, or None."""
    migrate(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM job_runs
            WHERE job_name = ?
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """,
            (job_name,),
        ).fetchone()
        return dict(row) if row else None


def get_latest_job_runs_map(
    job_names: Optional[Iterable[str]] = None, db_path: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Latest run per job name.
    If job_names is provided, only those jobs are returned (missing → omitted).
    """
    migrate(db_path)
    with _connect(db_path) as conn:
        if job_names is None:
            rows = conn.execute(
                """
                SELECT jr.* FROM job_runs jr
                INNER JOIN (
                    SELECT job_name, MAX(id) AS max_id
                    FROM job_runs
                    GROUP BY job_name
                ) latest ON jr.id = latest.max_id
                """
            ).fetchall()
        else:
            names = list(job_names)
            if not names:
                return {}
            placeholders = ",".join("?" * len(names))
            rows = conn.execute(
                f"""
                SELECT jr.* FROM job_runs jr
                INNER JOIN (
                    SELECT job_name, MAX(id) AS max_id
                    FROM job_runs
                    WHERE job_name IN ({placeholders})
                    GROUP BY job_name
                ) latest ON jr.id = latest.max_id
                """,
                names,
            ).fetchall()
        return {row["job_name"]: dict(row) for row in rows}


def insert_repo_stats_samples(
    samples: List[Dict[str, Any]],
    sampled_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Insert one repo_stats row per sample dict."""
    if not samples:
        return
    migrate(db_path)
    stamp = sampled_at or _utc_now_iso()
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO repo_stats (
                repo_name, sampled_at, total_size, snapshot_count,
                last_backup_at, last_snapshot_short_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    s.get("repo_name") or "",
                    stamp,
                    s.get("total_size"),
                    s.get("snapshot_count"),
                    s.get("last_backup_at") or None,
                    s.get("last_snapshot_short_id") or None,
                )
                for s in samples
                if s.get("repo_name")
            ],
        )


def save_dashboard_cache(
    payload: Dict[str, Any],
    db_path: Optional[str] = None,
    cache_key: str = CACHE_KEY,
) -> None:
    """Upsert dashboard_cache JSON blob."""
    migrate(db_path)
    updated = _utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO dashboard_cache (cache_key, updated_at, payload)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                updated_at = excluded.updated_at,
                payload = excluded.payload
            """,
            (cache_key, updated, json.dumps(payload)),
        )


def load_dashboard_cache(
    db_path: Optional[str] = None, cache_key: str = CACHE_KEY
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Load dashboard cache.
    Returns (updated_at, payload) or None if missing/invalid.
    """
    migrate(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT updated_at, payload FROM dashboard_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return row["updated_at"], payload


def extract_snapshot_short_id(stdout: str) -> Optional[str]:
    """Best-effort parse of restic JSON backup summary for snapshot_id."""
    if not stdout:
        return None
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("message_type") == "summary" or "snapshot_id" in data:
            sid = data.get("snapshot_id") or ""
            if sid:
                return sid[:8] if len(sid) > 8 else sid
    return None
