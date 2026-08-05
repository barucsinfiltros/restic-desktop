"""Modern UI components for Restic Manager."""

from ui.cards import SectionCard, StatCard
from ui.dashboard import create_dashboard_page, populate_jobs_table
from ui.sidebar import NavSidebar

__all__ = [
    "NavSidebar",
    "StatCard",
    "SectionCard",
    "create_dashboard_page",
    "populate_jobs_table",
]
