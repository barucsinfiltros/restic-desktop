"""Reusable Qt widgets and compatibility exports for the desktop pages."""

from importlib import import_module

from ui.cards import SectionCard, StatCard
from ui.sidebar import NavSidebar

_LEGACY_EXPORTS = {
    "RepositoryHealthDialog": "health_dialog",
    "create_dashboard_page": "dashboard",
    "create_repositories_page": "repositories",
    "create_snapshots_page": "snapshots",
    "create_restore_page": "restore",
    "create_backup_jobs_page": "backup_jobs",
    "create_retention_page": "retention",
    "create_logs_page": "logs",
    "create_settings_page": "settings",
    "populate_jobs_table": "dashboard",
    "populate_repository_table": "repositories",
    "populate_snapshots_table": "snapshots",
    "populate_backup_jobs_table": "backup_jobs",
}

__all__ = ["NavSidebar", "StatCard", "SectionCard", *_LEGACY_EXPORTS]


def __getattr__(name: str):
    """Load desktop pages only when requested through the public package API."""
    module = _LEGACY_EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value
