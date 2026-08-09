"""Modern dashboard page builder."""
from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.cards import SectionCard, StatCard
from ui.charts import DonutChart, RoundedBarChart
from ui.icons import tinted_icon
from ui.table_helpers import SortableTableItem, TableRowHover, make_repo_icon_cell

import ui.themes as themes

# Persist job identity on cells (survives display text / sort)
_JOB_NAME_ROLE = int(Qt.ItemDataRole.UserRole) + 90
_SNAPSHOT_ID_ROLE = int(Qt.ItemDataRole.UserRole) + 91
_REPO_TEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 92


def create_dashboard_page(
    host: Any,
    *,
    on_refresh: Optional[Callable[[], None]] = None,
    on_view_logs: Optional[Callable[[], None]] = None,
    on_new_backup: Optional[Callable[[], None]] = None,
    on_restore_files: Optional[Callable[[], None]] = None,
) -> QWidget:
    """
    Build the modern dashboard and attach widgets onto ``host``
    (``stats_labels``, chart widgets, ``jobs_table``, etc.).
    """
    page = QWidget()
    # Top-level QWidgets are visible by default; hide until reparented into the stack
    # so splash processEvents() cannot flash a tiny empty window during startup.
    page.setVisible(False)
    page.setObjectName("dashboardPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(16)

    # Header (refresh lives on the window title bar)
    header = QHBoxLayout()
    header.setSpacing(12)
    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Dashboard")
    title.setObjectName("pageTitle")
    title_col.addWidget(title)
    subtitle = QLabel("Welcome back! Here's an overview of your backup environment.")
    subtitle.setObjectName("pageSubtitle")
    title_col.addWidget(subtitle)
    host.dashboard_subtitle = subtitle
    header.addLayout(title_col, stretch=1)

    if on_new_backup is not None:
        new_backup = QPushButton("  New Backup")
        new_backup.setObjectName("titleBarActionBtn")
        new_backup.setFlat(True)
        new_backup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        new_backup.setIcon(tinted_icon("jobs.svg", "#8b95a5", 16))
        new_backup.setCursor(Qt.CursorShape.PointingHandCursor)
        new_backup.setFixedHeight(28)
        new_backup.clicked.connect(on_new_backup)
        header.addWidget(new_backup, 0, Qt.AlignmentFlag.AlignVCenter)
    if on_restore_files is not None:
        restore_files = QPushButton("  Restore Files")
        restore_files.setObjectName("titleBarActionBtn")
        restore_files.setFlat(True)
        restore_files.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        restore_files.setIcon(tinted_icon("restore.svg", "#8b95a5", 16))
        restore_files.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_files.setFixedHeight(28)
        restore_files.clicked.connect(on_restore_files)
        header.addWidget(restore_files, 0, Qt.AlignmentFlag.AlignVCenter)
    layout.addLayout(header)

    # Stat cards
    cards_row = QHBoxLayout()
    cards_row.setSpacing(12)
    cards_row.setAlignment(Qt.AlignmentFlag.AlignTop)
    host.stat_cards = {}
    host.stats_labels = {}

    card_specs = [
        ("total_repos", "Repositories", "repository.svg", "#3b82f6", "Total configured", False),
        ("total_snapshots", "Snapshots", "layers.svg", "#22c55e", "Total snapshots", False),
        ("total_size", "Total Size", "drive.svg", "#a855f7", "Of all backups", False),
        ("status", "Status", "health.svg", "#22c55e", "Click for health details", True),
    ]
    for key, title_text, icon_name, accent, sub, clickable in card_specs:
        card = StatCard(
            title_text,
            icon_name=icon_name,
            accent=accent,
            subtitle=sub,
            clickable=clickable,
            parent=page,
        )
        host.stat_cards[key] = card
        # Back-compat: existing code updates stats_labels[key].setText(...)
        host.stats_labels[key] = card.value_label
        if clickable:
            card.clicked.connect(host.open_repository_health_dialog)
        cards_row.addWidget(card, stretch=1)
    # Map last_backup updates onto status card value + subtitle
    host.stats_labels["last_backup"] = _StatusBridge(host)
    layout.addLayout(cards_row)

    # Charts (QPainter — always available)
    charts_row = QHBoxLayout()
    charts_row.setSpacing(12)

    size_card = SectionCard("Repository Storage Distribution", parent=page)
    size_card.setObjectName("chartCard")
    host.repo_size_chart = DonutChart(size_card)
    host.repo_size_chart.setMinimumHeight(240)
    size_card.body.addWidget(host.repo_size_chart, stretch=1)
    charts_row.addWidget(size_card, stretch=1)

    snap_card = SectionCard("Snapshots per Repository", parent=page)
    snap_card.setObjectName("chartCard")
    host.snapshot_count_chart = RoundedBarChart(snap_card)
    host.snapshot_count_chart.setMinimumHeight(240)
    snap_card.body.addWidget(host.snapshot_count_chart, stretch=1)
    charts_row.addWidget(snap_card, stretch=1)

    layout.addLayout(charts_row, stretch=1)

    # Recent backup jobs table
    jobs_card = SectionCard("Recent Backup Jobs", parent=page)
    jobs_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    if on_view_logs is not None:
        view_logs = QPushButton("View All Logs  >")
        view_logs.setObjectName("linkBtn")
        view_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        view_logs.setFlat(True)
        view_logs.setMinimumHeight(24)
        view_logs.clicked.connect(on_view_logs)
        jobs_card.header_actions.addWidget(view_logs)

    host.dashboard_jobs_table = QTableWidget()
    host.dashboard_jobs_table.setObjectName("jobsTable")
    host.dashboard_jobs_table.setColumnCount(8)
    host.dashboard_jobs_table.setHorizontalHeaderLabels(
        ["Repository", "Job Name", "Status", "Duration", "Last Backup", "Snapshot ID", "Size", "Schedule"]
    )
    host.dashboard_jobs_table.horizontalHeader().setStretchLastSection(True)
    host.dashboard_jobs_table.horizontalHeader().setSectionResizeMode(
        0, QHeaderView.ResizeMode.ResizeToContents
    )
    host.dashboard_jobs_table.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )
    for col in (2, 3, 4, 5, 6):
        host.dashboard_jobs_table.horizontalHeader().setSectionResizeMode(
            col, QHeaderView.ResizeMode.ResizeToContents
        )
    host.dashboard_jobs_table.horizontalHeader().setSectionResizeMode(
        7, QHeaderView.ResizeMode.ResizeToContents
    )
    host.dashboard_jobs_table.horizontalHeader().setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter
    )
    jobs_header = host.dashboard_jobs_table.horizontalHeader()
    jobs_header.setSectionsClickable(True)
    jobs_header.setSortIndicatorShown(True)
    jobs_header.setSortIndicator(4, Qt.SortOrder.DescendingOrder)
    host.dashboard_jobs_table.setSortingEnabled(True)
    host.dashboard_jobs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    host.dashboard_jobs_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    host.dashboard_jobs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    host.dashboard_jobs_table.setAlternatingRowColors(False)
    host.dashboard_jobs_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    host.dashboard_jobs_table.verticalHeader().setVisible(False)
    host.dashboard_jobs_table.setShowGrid(False)
    host.dashboard_jobs_table.setWordWrap(False)
    host.dashboard_jobs_table.setTextElideMode(Qt.TextElideMode.ElideNone)
    host.dashboard_jobs_table.setMinimumHeight(160)
    host.dashboard_jobs_table.verticalHeader().setDefaultSectionSize(48)
    host.dashboard_jobs_table.setMouseTracking(True)
    host.dashboard_jobs_table.viewport().setMouseTracking(True)
    host._jobs_table_hover = TableRowHover(
        host.dashboard_jobs_table,
        nudge_foreground=True,
        paint_background=False,
        lighten_amount=0.08,
    )
    host.dashboard_jobs_table.setContextMenuPolicy(
        Qt.ContextMenuPolicy.CustomContextMenu
    )
    host.dashboard_jobs_table.customContextMenuRequested.connect(
        lambda pos, t=host.dashboard_jobs_table: show_jobs_context_menu(
            host, t.viewport().mapToGlobal(pos)
        )
    )

    # Rounded inset shell so header + rows share one bordered box (mock style)
    jobs_shell = QFrame()
    jobs_shell.setObjectName("jobsTableShell")
    jobs_shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    shell_layout = QVBoxLayout(jobs_shell)
    shell_layout.setContentsMargins(0, 0, 0, 0)
    shell_layout.setSpacing(0)
    shell_layout.addWidget(host.dashboard_jobs_table)
    jobs_card.body.addWidget(jobs_shell, stretch=1)
    layout.addWidget(jobs_card, stretch=1)

    # Stash for refresh helpers
    host.refresh_dashboard_jobs_table = lambda: populate_jobs_table(host)

    return page


class _StatusBridge:
    """Adapt last_backup string updates onto the Status stat card."""

    def __init__(self, host: Any):
        self._host = host

    def setText(self, text: str) -> None:  # noqa: N802 — Qt naming
        card = self._host.stat_cards.get("status")
        if not card:
            return
        if text in ("Loading...", "…"):
            card.set_value("…")
            card.set_subtitle("Refreshing…")
            return
        # Prefer real health aggregate when available
        if hasattr(self._host, "refresh_dashboard_health_status"):
            self._host.refresh_dashboard_health_status(fallback_last_backup=text)
            return
        from ui.dashboard import format_relative_time, format_relative_time_short

        if not text or text in ("—", "Never"):
            card.set_value("—")
            card.set_subtitle("No recent backup" if text == "Never" else "Last backup")
            return
        card.set_value("Healthy")
        short = format_relative_time_short(text)
        full = format_relative_time(text)
        card.set_subtitle(f"Last Backup: {short}", tooltip=full)


def _parse_timestamp(value: str):
    """Best-effort parse of ISO / common restic timestamps to aware UTC datetime."""
    from datetime import datetime, timezone

    text = (value or "").strip()
    if not text or text == "—":
        return None
    # Normalize Zulu / space separators
    candidates = [
        text,
        text.replace("Z", "+00:00"),
        text.replace(" ", "T", 1),
    ]
    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def format_relative_time(value: str) -> str:
    """Return e.g. '2 hours ago' with absolute time as fallback detail."""
    from datetime import datetime, timezone

    dt = _parse_timestamp(value)
    if dt is None:
        return value if value else "—"

    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0

    if seconds < 60:
        relative = "just now"
    elif seconds < 3600:
        mins = seconds // 60
        relative = f"{mins} minute{'s' if mins != 1 else ''} ago"
    elif seconds < 86400:
        hours = seconds // 3600
        relative = f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 86400 * 30:
        days = seconds // 86400
        relative = f"{days} day{'s' if days != 1 else ''} ago"
    else:
        months = max(1, seconds // (86400 * 30))
        relative = f"{months} month{'s' if months != 1 else ''} ago"

    absolute = dt.astimezone().strftime("%Y-%m-%d %H:%M")
    return f"{relative} ({absolute})"


def format_relative_time_short(value: str) -> str:
    """Relative time only (no absolute timestamp) for compact table cells."""
    full = format_relative_time(value)
    if full in ("—", "Never") or " ago" not in full:
        return full
    return full.split(" (", 1)[0]


def _job_from_table_row(host: Any, row: int) -> tuple[dict | None, str, str]:
    """Return (job_dict_or_None, job_name, snapshot_id) for a dashboard jobs row."""
    table = getattr(host, "dashboard_jobs_table", None)
    if table is None or row < 0:
        return None, "", ""
    name_item = table.item(row, 1)
    snap_item = table.item(row, 5)
    job_name = ""
    if name_item is not None:
        job_name = str(name_item.data(_JOB_NAME_ROLE) or name_item.text() or "").strip()
    snap_id = ""
    if snap_item is not None:
        snap_id = str(
            snap_item.data(_SNAPSHOT_ID_ROLE) or snap_item.text() or ""
        ).strip()
        if snap_id == "—":
            snap_id = ""
    job = None
    if job_name and hasattr(host, "settings_manager"):
        jobs = host.settings_manager.get("backup_jobs") or []
        job = next((j for j in jobs if j.get("name") == job_name), None)
    return job, job_name, snap_id


def show_jobs_context_menu(host: Any, global_pos) -> None:
    """Right-click menu for Recent Backup Jobs rows."""
    from ui.rounded_menu import RoundedMenu

    table = getattr(host, "dashboard_jobs_table", None)
    if table is None:
        return
    index = table.indexAt(table.viewport().mapFromGlobal(global_pos))
    if not index.isValid():
        return
    row = index.row()
    table.selectRow(row)
    job, job_name, snap_id = _job_from_table_row(host, row)
    if not job_name:
        return

    menu = RoundedMenu(table)
    run_act = menu.addAction("Run job")
    edit_act = menu.addAction("Edit job")
    menu.addSeparator()
    copy_act = menu.addAction("Copy snapshot ID")
    copy_act.setEnabled(bool(snap_id))
    details_act = menu.addAction("Last run details…")
    chosen = menu.exec(global_pos)
    if chosen is None:
        return

    if chosen is run_act:
        if job is None:
            QMessageBox.warning(table, "Job Not Found", f"Job '{job_name}' was not found.")
            return
        if hasattr(host, "run_backup_job"):
            host.run_backup_job(job)
        return

    if chosen is edit_act:
        if job is None:
            QMessageBox.warning(table, "Job Not Found", f"Job '{job_name}' was not found.")
            return
        if hasattr(host, "edit_backup_job"):
            host.edit_backup_job(job)
            if hasattr(host, "refresh_dashboard_jobs_table"):
                host.refresh_dashboard_jobs_table()
        return

    if chosen is copy_act:
        if not snap_id:
            return
        QGuiApplication.clipboard().setText(snap_id)
        if hasattr(host, "log"):
            host.log(f"Copied snapshot ID: {snap_id}")
        return

    if chosen is details_act:
        _show_last_run_details(host, job_name, parent=table)


def _show_last_run_details(host: Any, job_name: str, *, parent=None) -> None:
    """Show the latest job_runs row for a job."""
    try:
        import core.history_db as history_db
    except ImportError:
        QMessageBox.information(parent, "Last Run Details", "History database is not available.")
        return

    db_path = None
    if hasattr(host, "_history_db_path"):
        try:
            db_path = host._history_db_path()
        except Exception:
            db_path = None
    try:
        row = history_db.get_latest_job_run(job_name, db_path=db_path)
    except Exception as exc:
        QMessageBox.warning(parent, "Last Run Details", f"Could not read history:\n{exc}")
        return

    if not row:
        QMessageBox.information(
            parent,
            "Last Run Details",
            f"No recorded runs for '{job_name}' yet.\n\n"
            "Run the job from the GUI, CLI, or a scheduled task to create history.",
        )
        return

    status = "Success" if row.get("success") else "Failed"
    duration = history_db.format_duration(row.get("duration_sec"))
    error = (row.get("error_summary") or "").strip() or "—"
    snap = (row.get("snapshot_short_id") or "").strip() or "—"
    lines = [
        f"Job: {row.get('job_name') or job_name}",
        f"Repository: {row.get('repo_name') or '—'}",
        f"Status: {status}",
        f"Duration: {duration}",
        f"Started: {row.get('started_at') or '—'}",
        f"Finished: {row.get('finished_at') or '—'}",
        f"Source: {row.get('source') or '—'}",
        f"Exit code: {row.get('exit_code') if row.get('exit_code') is not None else '—'}",
        f"Snapshot: {snap}",
        f"Error: {error}",
    ]
    QMessageBox.information(parent, "Last Run Details", "\n".join(lines))


def populate_jobs_table(host: Any) -> None:
    """Fill dashboard jobs table from settings_manager backup_jobs."""
    table = getattr(host, "dashboard_jobs_table", None)
    if table is None or not hasattr(host, "settings_manager"):
        return
    jobs = host.settings_manager.get("backup_jobs") or []
    repositories = host.settings_manager.get("repositories") or []
    if themes.ensure_repo_colors(repositories):
        host.settings_manager.set("repositories", repositories)
        host.settings_manager.save_settings()
    repo_last = getattr(host, "_repo_last_backup", {}) or {}
    repo_snaps = getattr(host, "_repo_last_snapshot", {}) or {}
    repo_sizes = getattr(host, "_repo_sizes", {}) or {}

    latest_runs: dict = {}
    try:
        import core.history_db as history_db

        db_path = None
        if hasattr(host, "_history_db_path"):
            try:
                db_path = host._history_db_path()
            except Exception:
                db_path = None
        names = [j.get("name") for j in jobs if j.get("name")]
        latest_runs = history_db.get_latest_job_runs_map(names, db_path=db_path)
    except Exception:
        latest_runs = {}

    header = table.horizontalHeader()
    sort_col = header.sortIndicatorSection()
    sort_order = header.sortIndicatorOrder()
    if sort_col < 0:
        sort_col = 4
        sort_order = Qt.SortOrder.DescendingOrder
    # Reset row hover before rebuilding cells
    hover = getattr(host, "_jobs_table_hover", None)
    if hover is not None:
        hover._apply(-1)
    was_sorting = table.isSortingEnabled()
    table.setSortingEnabled(False)
    table.clearContents()
    table.setRowCount(len(jobs))
    status_rank = {"Success": 4, "Failed": 3, "Scheduled": 2, "Ready": 1}
    left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    try:
        theme_id = themes.resolve_theme_id(host.settings_manager.get("theme"))
        app_theme = themes.get_app_theme(theme_id)
        # Soft secondary text: theme muted, nudged slightly toward primary for readability.
        muted = themes._mix_hex(app_theme.muted, app_theme.text, 0.18)
        success_color = app_theme.ok
        failed_color = app_theme.danger
    except Exception:
        muted = "#9aa3b2"
        success_color = "#15803d"
        failed_color = "#ef4444"
    muted_color = QColor(muted)

    def _format_size(nbytes: int) -> str:
        fmt = getattr(host, "format_bytes", None)
        if callable(fmt) and nbytes > 0:
            return fmt(nbytes)
        if nbytes <= 0:
            return "—"
        value = float(nbytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024.0:
                return f"{value:.2f} {unit}"
            value /= 1024.0
        return f"{value:.2f} PB"

    for row, job in enumerate(jobs):
        repos = job.get("repositories") or []
        if not repos and job.get("repository"):
            repos = [job.get("repository")]
        repo_text = ", ".join(repos) if repos else "—"
        schedule = job.get("schedule") or {}
        if schedule.get("enabled"):
            sched_text = f"{schedule.get('frequency', '?')} @ {schedule.get('time', '?')}"
        else:
            sched_text = "Manual"

        # Prefer live restic snapshot times/ids, then persisted job fields
        last_run = schedule.get("last_run") or job.get("last_run") or ""
        snap_short = job.get("last_snapshot_id") or ""
        snap_full = job.get("last_snapshot_full_id") or ""
        best_live = ""
        best_live_snap = None
        size_bytes = 0
        for name in repos:
            stamp = repo_last.get(name) or ""
            if stamp and (not best_live or stamp > best_live):
                best_live = stamp
                best_live_snap = repo_snaps.get(name)
            size_bytes = max(size_bytes, int(repo_sizes.get(name) or 0))
        if best_live and (not last_run or best_live > str(last_run)):
            last_run = best_live
        if best_live_snap and best_live_snap.get("short_id"):
            snap_short = best_live_snap["short_id"]
            snap_full = best_live_snap.get("id") or snap_short
        if not last_run:
            last_run = "—"
        snap_text = snap_short or "—"
        size_text = _format_size(size_bytes)

        job_name = job.get("name", "—") or "—"
        last_hist = latest_runs.get(job_name)
        duration_text = "—"
        duration_sec = -1.0
        if last_hist is not None:
            try:
                import core.history_db as _history_db

                duration_text = _history_db.format_duration(last_hist.get("duration_sec"))
            except Exception:
                duration_text = "—"
            try:
                duration_sec = float(last_hist.get("duration_sec"))
            except (TypeError, ValueError):
                duration_sec = -1.0

        status = "Scheduled" if schedule.get("enabled") else "Ready"
        if last_hist is not None:
            status = "Success" if last_hist.get("success") else "Failed"
        last_display = (
            format_relative_time_short(str(last_run)) if last_run != "—" else "Never"
        )
        last_sort = 0.0
        if last_run and last_run != "—":
            parsed = _parse_timestamp(str(last_run))
            if parsed is not None:
                last_sort = parsed.timestamp()

        # Repo cell text is hidden under the icon widget to avoid ghosted/ellided text.
        values = [
            "",
            job_name,
            status,
            duration_text,
            last_display,
            snap_text,
            size_text,
            sched_text,
        ]
        for col, value in enumerate(values):
            item = SortableTableItem(value)
            # Force leading alignment (stylesheet text-align is unreliable on Fusion)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter
            )
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, repo_text.lower())
                item.setData(_JOB_NAME_ROLE, job_name)
                item.setData(_REPO_TEXT_ROLE, repo_text)
            elif col == 1:
                item.setData(_JOB_NAME_ROLE, job_name)
            elif col == 2:
                item.setData(Qt.ItemDataRole.UserRole, status_rank.get(status, 0))
                item.setData(_JOB_NAME_ROLE, job_name)
            elif col == 3:
                item.setData(Qt.ItemDataRole.UserRole, duration_sec)
            elif col == 4:
                item.setData(Qt.ItemDataRole.UserRole, last_sort)
            elif col == 5:
                item.setData(
                    _SNAPSHOT_ID_ROLE,
                    snap_full or (snap_short if snap_short and snap_short != "—" else ""),
                )
            elif col == 6:
                item.setData(Qt.ItemDataRole.UserRole, size_bytes)
            if col == 1:
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
            if col == 2 and status == "Success":
                item.setForeground(QColor(success_color))
                item.setData(TableRowHover.LOCKED_FG_ROLE, success_color)
            elif col == 2 and status == "Failed":
                item.setForeground(QColor(failed_color))
                item.setData(TableRowHover.LOCKED_FG_ROLE, failed_color)
            if col == 3:
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
            if col == 4 and last_run and last_run != "—":
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
                item.setToolTip(str(last_run))
            elif col == 4:
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
            if col == 5 and snap_full:
                item.setToolTip(str(snap_full))
            if col == 6:
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
            if col == 7:
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
            table.setItem(row, col, item)

        repo_cell = make_repo_icon_cell(
            list(repos),
            lambda n, repos=repositories: themes.repo_color_for_name(n, repos),
            parent=table,
        )
        repo_cell.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        repo_cell.customContextMenuRequested.connect(
            lambda pos, w=repo_cell: show_jobs_context_menu(host, w.mapToGlobal(pos))
        )
        table.setCellWidget(row, 0, repo_cell)
    table.setSortingEnabled(was_sorting)
    if was_sorting:
        table.sortItems(sort_col, sort_order)
        header.setSortIndicator(sort_col, sort_order)
