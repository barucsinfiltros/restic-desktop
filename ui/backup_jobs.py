"""Modern backup jobs page builder."""
from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.rounded_menu import RoundedMenu
from ui.cards import SectionCard
from ui.icons import tinted_icon
from ui.table_helpers import SortableTableItem, TableRowHover, make_repo_icon_cell

import ui.themes as themes

# Columns: Name, Repository, Paths, Schedule, menu
_COL_NAME = 0
_COL_REPO = 1
_COL_PATHS = 2
_COL_SCHEDULE = 3
_COL_MENU = 4

_JOB_NAME_ROLE = int(Qt.ItemDataRole.UserRole) + 90


def create_backup_jobs_page(host: Any) -> QWidget:
    """Build the backup jobs page and attach widgets onto ``host``."""
    page = QWidget()
    page.setVisible(False)
    page.setObjectName("backupJobsPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(16)

    header = QHBoxLayout()
    header.setSpacing(12)
    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Backup Jobs")
    title.setObjectName("pageTitle")
    title_col.addWidget(title)
    subtitle = QLabel("Create and schedule backups across one or more repositories.")
    subtitle.setObjectName("pageSubtitle")
    title_col.addWidget(subtitle)
    header.addLayout(title_col, stretch=1)
    if callable(getattr(host, "open_staged_catalog", None)):
        catalog_button = QPushButton("Catálogo en preparación")
        catalog_button.clicked.connect(host.open_staged_catalog)
        header.addWidget(catalog_button)
    # New Job lives on the window title bar (same pattern as Add Repository).
    layout.addLayout(header)

    table_card = SectionCard("Configured Jobs", parent=page)
    table_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    host.backup_jobs_table = QTableWidget()
    host.backup_jobs_table.setObjectName("backupJobsTable")
    host.backup_jobs_table.setColumnCount(5)
    host.backup_jobs_table.setHorizontalHeaderLabels(
        ["Job Name", "Repository", "Paths", "Schedule", ""]
    )
    jobs_header = host.backup_jobs_table.horizontalHeader()
    jobs_header.setStretchLastSection(False)
    jobs_header.setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter
    )
    jobs_header.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)
    jobs_header.setSectionResizeMode(_COL_REPO, QHeaderView.ResizeMode.ResizeToContents)
    jobs_header.setSectionResizeMode(_COL_PATHS, QHeaderView.ResizeMode.Stretch)
    jobs_header.setSectionResizeMode(_COL_SCHEDULE, QHeaderView.ResizeMode.ResizeToContents)
    jobs_header.setSectionResizeMode(_COL_MENU, QHeaderView.ResizeMode.Fixed)
    host.backup_jobs_table.setColumnWidth(_COL_MENU, 52)
    jobs_header.setSectionsClickable(True)
    jobs_header.setSortIndicatorShown(True)
    jobs_header.setSortIndicator(_COL_NAME, Qt.SortOrder.AscendingOrder)
    host.backup_jobs_table.setSortingEnabled(False)
    host.backup_jobs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    host.backup_jobs_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    host.backup_jobs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    host.backup_jobs_table.setAlternatingRowColors(False)
    host.backup_jobs_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    host.backup_jobs_table.verticalHeader().setVisible(False)
    host.backup_jobs_table.setShowGrid(False)
    host.backup_jobs_table.setWordWrap(False)
    host.backup_jobs_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
    host.backup_jobs_table.setMinimumHeight(200)
    host.backup_jobs_table.verticalHeader().setDefaultSectionSize(60)
    host.backup_jobs_table.setMouseTracking(True)
    host.backup_jobs_table.viewport().setMouseTracking(True)
    host._backup_jobs_table_hover = TableRowHover(
        host.backup_jobs_table,
        nudge_foreground=True,
        paint_background=False,
        lighten_amount=0.08,
    )

    table_shell = QFrame()
    table_shell.setObjectName("backupJobsTableShell")
    table_shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    shell_layout = QVBoxLayout(table_shell)
    shell_layout.setContentsMargins(0, 0, 0, 0)
    shell_layout.setSpacing(0)
    shell_layout.addWidget(host.backup_jobs_table)
    table_card.body.addWidget(table_shell, stretch=1)
    layout.addWidget(table_card, stretch=1)

    def _resort(column: int) -> None:
        if column >= _COL_MENU:
            return
        header = host.backup_jobs_table.horizontalHeader()
        if header.sortIndicatorSection() == column:
            new_order = (
                Qt.SortOrder.AscendingOrder
                if header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
                else Qt.SortOrder.DescendingOrder
            )
        else:
            new_order = Qt.SortOrder.AscendingOrder
        header.setSortIndicator(column, new_order)
        populate_backup_jobs_table(host)

    jobs_header.sectionClicked.connect(_resort)

    return page


def _job_repositories(job: dict) -> list[str]:
    repositories = job.get("repositories") or []
    if not repositories:
        repo = job.get("repository") or ""
        repositories = [repo] if repo else []
    return [r for r in repositories if r]


def _schedule_text(job: dict) -> str:
    schedule = job.get("schedule") or {}
    if not schedule.get("enabled"):
        return "Manual"
    freq = (schedule.get("frequency") or "daily").capitalize()
    time = schedule.get("time") or "00:00"
    if freq == "Weekly":
        days = schedule.get("days") or []
        days_str = ", ".join(days) if days else "All days"
        return f"{freq} at {time} ({days_str})"
    if freq == "Monthly":
        day_of_month = schedule.get("day_of_month", 1)
        return f"{freq} at {time} (Day {day_of_month})"
    return f"{freq} at {time}"


def _paths_text(job: dict) -> tuple[str, str]:
    paths = job.get("paths") or []
    if not paths:
        return "No paths", ""
    if len(paths) == 1:
        return paths[0], paths[0]
    summary = f"{len(paths)} paths: {paths[0]} +{len(paths) - 1} more"
    tip = "\n".join(paths)
    return summary, tip


def _job_sort_key(job: dict, column: int):
    if column == _COL_NAME:
        return (job.get("name") or "").lower()
    if column == _COL_REPO:
        return ", ".join(_job_repositories(job)).lower()
    if column == _COL_PATHS:
        return _paths_text(job)[0].lower()
    if column == _COL_SCHEDULE:
        return _schedule_text(job).lower()
    return ""


def _make_job_menu_cell(
    job: dict,
    *,
    on_run: Callable[[dict], None],
    on_edit: Callable[[dict], None],
    on_delete: Callable[[dict], None],
    icon_color: str,
    parent=None,
) -> QWidget:
    """Kebab (⋯) button that opens Run / Edit / Delete."""
    cell = QWidget(parent)
    cell.setObjectName("jobActions")
    row = QHBoxLayout(cell)
    row.setContentsMargins(0, 0, 8, 0)
    row.setSpacing(0)
    row.addStretch(1)

    btn = QPushButton(cell)
    btn.setObjectName("iconMenuBtn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Actions")
    btn.setFlat(True)
    btn.setFixedSize(32, 32)
    btn.setIcon(tinted_icon("more_horiz.svg", icon_color, 18))
    btn.setIconSize(QSize(18, 18))

    def _open_menu(_checked: bool = False, button: QPushButton = btn) -> None:
        menu = RoundedMenu(button)
        run_act = menu.addAction("Run")
        edit_act = menu.addAction("Edit")
        menu.addSeparator()
        delete_act = menu.addAction("Delete")
        chosen = menu.exec(button.mapToGlobal(button.rect().bottomRight()))
        if chosen is run_act:
            on_run(job)
        elif chosen is edit_act:
            on_edit(job)
        elif chosen is delete_act:
            on_delete(job)

    btn.clicked.connect(_open_menu)
    row.addWidget(btn)
    return cell


def populate_backup_jobs_table(
    host: Any,
    *,
    on_run: Optional[Callable[[dict], None]] = None,
    on_edit: Optional[Callable[[dict], None]] = None,
    on_delete: Optional[Callable[[dict], None]] = None,
) -> None:
    """Fill the backup jobs table from settings."""
    table = getattr(host, "backup_jobs_table", None)
    if table is None or not hasattr(host, "settings_manager"):
        return

    on_run = on_run or getattr(host, "run_backup_job", None)
    on_edit = on_edit or getattr(host, "edit_backup_job", None)
    on_delete = on_delete or getattr(host, "delete_backup_job", None)
    if on_run is None or on_edit is None or on_delete is None:
        return

    jobs = list(host.settings_manager.get("backup_jobs") or [])
    repositories = list(host.settings_manager.get("repositories") or [])
    if themes.ensure_repo_colors(repositories):
        host.settings_manager.set("repositories", repositories)
        host.settings_manager.save_settings()

    header = table.horizontalHeader()
    sort_col = header.sortIndicatorSection()
    sort_order = header.sortIndicatorOrder()
    if sort_col < 0 or sort_col >= _COL_MENU:
        sort_col = _COL_NAME
        sort_order = Qt.SortOrder.AscendingOrder

    reverse = sort_order == Qt.SortOrder.DescendingOrder
    jobs.sort(key=lambda j: _job_sort_key(j, sort_col), reverse=reverse)

    hover = getattr(host, "_backup_jobs_table_hover", None)
    if hover is not None:
        hover._apply(-1)

    try:
        theme_id = themes.resolve_theme_id(host.settings_manager.get("theme"))
        app_theme = themes.get_app_theme(theme_id)
        muted = themes._mix_hex(app_theme.muted, app_theme.text, 0.18)
        menu_icon = app_theme.muted
    except Exception:
        muted = "#9aa3b2"
        menu_icon = "#8b95a5"
    muted_color = QColor(muted)
    left = Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter

    table.setRowCount(len(jobs))

    for row, job in enumerate(jobs):
        name = job.get("name", "") or "—"
        repos = _job_repositories(job)
        paths_text, paths_tip = _paths_text(job)
        schedule_text = _schedule_text(job)

        values = [name, "", paths_text, schedule_text, ""]
        for col, value in enumerate(values):
            item = SortableTableItem(value)
            item.setTextAlignment(left)
            if col == _COL_NAME:
                item.setData(Qt.ItemDataRole.UserRole, name.lower())
                item.setData(_JOB_NAME_ROLE, name)
            elif col == _COL_REPO:
                item.setData(Qt.ItemDataRole.UserRole, ", ".join(repos).lower())
            elif col == _COL_PATHS:
                item.setData(Qt.ItemDataRole.UserRole, paths_text.lower())
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
                if paths_tip:
                    item.setToolTip(paths_tip)
            elif col == _COL_SCHEDULE:
                item.setData(Qt.ItemDataRole.UserRole, schedule_text.lower())
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
            table.setItem(row, col, item)

        table.setCellWidget(
            row,
            _COL_REPO,
            make_repo_icon_cell(
                repos,
                lambda n, repos=repositories: themes.repo_color_for_name(n, repos),
                parent=table,
            ),
        )
        table.setRowHeight(row, 60)
        table.setCellWidget(
            row,
            _COL_MENU,
            _make_job_menu_cell(
                job,
                on_run=on_run,
                on_edit=on_edit,
                on_delete=on_delete,
                icon_color=menu_icon,
                parent=table,
            ),
        )

    table.resizeColumnToContents(_COL_REPO)
    table.setColumnWidth(_COL_REPO, max(table.columnWidth(_COL_REPO), 160))
    table.resizeColumnToContents(_COL_SCHEDULE)
    table.setColumnWidth(_COL_MENU, 52)
    header.setSortIndicator(sort_col, sort_order)
