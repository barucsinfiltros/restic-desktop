"""Modern UI components for Restic Manager."""

from ui.cards import SectionCard, StatCard
from ui.dashboard import create_dashboard_page, populate_jobs_table
from ui.repositories import create_repositories_page, populate_repository_table
from ui.sidebar import NavSidebar
from ui.snapshots import create_snapshots_page, populate_snapshots_table

__all__ = [
    "NavSidebar",
    "StatCard",
    "SectionCard",
    "create_dashboard_page",
    "create_repositories_page",
    "create_snapshots_page",
    "populate_jobs_table",
    "populate_repository_table",
    "populate_snapshots_table",
]
