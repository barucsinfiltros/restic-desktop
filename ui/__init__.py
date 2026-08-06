"""Modern UI components for Restic Manager."""

from ui.backup_jobs import create_backup_jobs_page, populate_backup_jobs_table
from ui.cards import SectionCard, StatCard
from ui.dashboard import create_dashboard_page, populate_jobs_table
from ui.logs import create_logs_page
from ui.repositories import create_repositories_page, populate_repository_table
from ui.retention import create_retention_page
from ui.sidebar import NavSidebar
from ui.snapshots import create_snapshots_page, populate_snapshots_table
from ui.restore import create_restore_page

__all__ = [
    "NavSidebar",
    "StatCard",
    "SectionCard",
    "create_dashboard_page",
    "create_repositories_page",
    "create_snapshots_page",
    "create_restore_page",
    "create_backup_jobs_page",
    "create_retention_page",
    "create_logs_page",
    "populate_jobs_table",
    "populate_repository_table",
    "populate_snapshots_table",
    "populate_backup_jobs_table",
]
