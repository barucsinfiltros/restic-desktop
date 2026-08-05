"""Modern dashboard page builder."""
from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.cards import SectionCard, StatCard

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure

    _MPL = True
except Exception:
    try:
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure

        _MPL = True
    except Exception:
        _MPL = False
        FigureCanvas = None  # type: ignore
        Figure = None  # type: ignore


def create_dashboard_page(
    host: Any,
    *,
    matplotlib_available: bool,
    on_refresh: Optional[Callable[[], None]] = None,
    on_view_logs: Optional[Callable[[], None]] = None,
) -> QWidget:
    """
    Build the modern dashboard and attach widgets onto ``host``
    (``stats_labels``, chart canvases, ``jobs_table``, etc.).
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
    layout.addLayout(header)

    # Stat cards
    cards_row = QHBoxLayout()
    cards_row.setSpacing(12)
    host.stat_cards = {}
    host.stats_labels = {}

    card_specs = [
        ("total_repos", "Repositories", "repository.svg", "#3b82f6", "Total configured"),
        ("total_snapshots", "Snapshots", "snapshot.svg", "#22c55e", "Total snapshots"),
        ("total_size", "Total Size", "storage.svg", "#a855f7", "Of all backups"),
        ("status", "Status", "health.svg", "#22c55e", "Last backup"),
    ]
    for key, title_text, icon_name, accent, sub in card_specs:
        card = StatCard(
            title_text,
            icon_name=icon_name,
            accent=accent,
            subtitle=sub,
            parent=page,
        )
        host.stat_cards[key] = card
        # Back-compat: existing code updates stats_labels[key].setText(...)
        host.stats_labels[key] = card.value_label
        cards_row.addWidget(card)
    # Map last_backup updates onto status card value + subtitle
    host.stats_labels["last_backup"] = _StatusBridge(host)
    layout.addLayout(cards_row)

    # Charts
    if matplotlib_available and _MPL and FigureCanvas is not None:
        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)

        size_card = SectionCard("Repository Storage Distribution", parent=page)
        size_card.setObjectName("chartCard")
        host.repo_size_canvas = FigureCanvas(Figure(figsize=(5.5, 3.2), dpi=100))
        host.repo_size_canvas.setMinimumHeight(240)
        host.repo_size_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        size_card.body.addWidget(host.repo_size_canvas, stretch=1)
        charts_row.addWidget(size_card, stretch=1)

        snap_card = SectionCard("Snapshots per Repository", parent=page)
        snap_card.setObjectName("chartCard")
        host.snapshot_count_canvas = FigureCanvas(Figure(figsize=(5.5, 3.2), dpi=100))
        host.snapshot_count_canvas.setMinimumHeight(240)
        host.snapshot_count_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        snap_card.body.addWidget(host.snapshot_count_canvas, stretch=1)
        charts_row.addWidget(snap_card, stretch=1)

        layout.addLayout(charts_row, stretch=1)
        # Chart draw is deferred until the page is in the stacked widget (avoids flash).
    else:
        # Keep attributes absent; existing code guards with hasattr
        pass

    # Recent backup jobs table
    jobs_card = SectionCard("Recent Backup Jobs", parent=page)
    jobs_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    if on_view_logs is not None:
        view_logs = QPushButton("View All Logs  >")
        view_logs.setObjectName("linkBtn")
        view_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        view_logs.clicked.connect(on_view_logs)
        jobs_card.header_actions.addWidget(view_logs)

    host.dashboard_jobs_table = QTableWidget()
    host.dashboard_jobs_table.setObjectName("jobsTable")
    host.dashboard_jobs_table.setColumnCount(6)
    host.dashboard_jobs_table.setHorizontalHeaderLabels(
        ["Repository", "Job Name", "Status", "Last Backup", "Snapshot ID", "Schedule"]
    )
    host.dashboard_jobs_table.horizontalHeader().setStretchLastSection(True)
    host.dashboard_jobs_table.horizontalHeader().setSectionResizeMode(
        0, QHeaderView.ResizeMode.ResizeToContents
    )
    host.dashboard_jobs_table.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )
    jobs_header = host.dashboard_jobs_table.horizontalHeader()
    jobs_header.setSectionsClickable(True)
    jobs_header.setSortIndicatorShown(True)
    jobs_header.setSortIndicator(3, Qt.SortOrder.DescendingOrder)
    host.dashboard_jobs_table.setSortingEnabled(True)
    host.dashboard_jobs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    host.dashboard_jobs_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    host.dashboard_jobs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    host.dashboard_jobs_table.setAlternatingRowColors(False)
    host.dashboard_jobs_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    host.dashboard_jobs_table.verticalHeader().setVisible(False)
    host.dashboard_jobs_table.setShowGrid(False)
    host.dashboard_jobs_table.setMinimumHeight(160)
    host.dashboard_jobs_table.verticalHeader().setDefaultSectionSize(44)
    host.dashboard_jobs_table.setMouseTracking(True)
    host.dashboard_jobs_table.viewport().setMouseTracking(True)
    host._jobs_table_hover = _JobsRowHover(host.dashboard_jobs_table)

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


class _JobsSortItem(QTableWidgetItem):
    """Table cell that sorts by UserRole when set (e.g. timestamps)."""

    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        if other is None:
            return False
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole)
        if left is not None and right is not None:
            try:
                return left < right
            except TypeError:
                pass
        return super().__lt__(other)


class _JobsRowHover(QObject):
    """Highlight the full table row on hover (Qt stylesheets are cell-only)."""

    def __init__(self, table: QTableWidget):
        super().__init__(table)
        self._table = table
        self._row = -1
        self._hover = QBrush(QColor(255, 255, 255, 16))
        table.viewport().installEventFilter(self)
        table.destroyed.connect(self._on_table_destroyed)

    def _on_table_destroyed(self, *_args) -> None:
        self._table = None
        self._row = -1

    def set_hover_brush(self, brush: QBrush) -> None:
        self._hover = brush

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        table = self._table
        if table is None:
            return False
        try:
            viewport = table.viewport()
        except RuntimeError:
            self._table = None
            return False
        if obj is not viewport:
            return False
        et = event.type()
        if et == QEvent.Type.MouseMove:
            index = table.indexAt(event.position().toPoint())
            row = index.row() if index.isValid() else -1
            if row != self._row:
                self._apply(row)
        elif et == QEvent.Type.Leave:
            self._apply(-1)
        return False

    def _apply(self, row: int) -> None:
        table = self._table
        if table is None:
            return
        try:
            cols = table.columnCount()
        except RuntimeError:
            self._table = None
            return
        prev = self._row
        self._row = row
        for r in (prev, row):
            if r < 0:
                continue
            for c in range(cols):
                item = table.item(r, c)
                if item is None:
                    continue
                if r == row and not item.isSelected():
                    item.setBackground(self._hover)
                else:
                    item.setBackground(QBrush())


class _StatusBridge:
    """Adapt last_backup string updates onto the Status stat card."""

    def __init__(self, host: Any):
        self._host = host

    def setText(self, text: str) -> None:  # noqa: N802 — Qt naming
        from ui.dashboard import format_relative_time

        card = self._host.stat_cards.get("status")
        if not card:
            return
        if not text or text in ("—", "Never", "Loading..."):
            card.set_value("—" if text != "Loading..." else "…")
            card.set_subtitle("No recent backup" if text == "Never" else "Last backup")
            if text == "Loading...":
                card.set_value("…")
                card.set_subtitle("Refreshing…")
            return
        card.set_value("Healthy")
        card.set_subtitle(f"Last Backup: {format_relative_time(text)}")


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


def populate_jobs_table(host: Any) -> None:
    """Fill dashboard jobs table from settings_manager backup_jobs."""
    table = getattr(host, "dashboard_jobs_table", None)
    if table is None or not hasattr(host, "settings_manager"):
        return
    jobs = host.settings_manager.get("backup_jobs") or []
    repo_last = getattr(host, "_repo_last_backup", {}) or {}
    repo_snaps = getattr(host, "_repo_last_snapshot", {}) or {}
    header = table.horizontalHeader()
    sort_col = header.sortIndicatorSection()
    sort_order = header.sortIndicatorOrder()
    if sort_col < 0:
        sort_col = 3
        sort_order = Qt.SortOrder.DescendingOrder
    # Reset row hover before rebuilding cells
    hover = getattr(host, "_jobs_table_hover", None)
    if hover is not None:
        hover._apply(-1)
    was_sorting = table.isSortingEnabled()
    table.setSortingEnabled(False)
    table.setRowCount(len(jobs))
    status_rank = {"Success": 3, "Scheduled": 2, "Ready": 1}
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
        for name in repos:
            stamp = repo_last.get(name) or ""
            if stamp and (not best_live or stamp > best_live):
                best_live = stamp
                best_live_snap = repo_snaps.get(name)
        if best_live and (not last_run or best_live > str(last_run)):
            last_run = best_live
        if best_live_snap and best_live_snap.get("short_id"):
            snap_short = best_live_snap["short_id"]
            snap_full = best_live_snap.get("id") or snap_short
        if not last_run:
            last_run = "—"
        snap_text = snap_short or "—"

        status = "Scheduled" if schedule.get("enabled") else "Ready"
        if last_run and last_run != "—":
            status = "Success"
        last_display = format_relative_time(str(last_run)) if last_run != "—" else "Never"
        last_sort = 0.0
        if last_run and last_run != "—":
            parsed = _parse_timestamp(str(last_run))
            if parsed is not None:
                last_sort = parsed.timestamp()

        values = [repo_text, job.get("name", "—"), status, last_display, snap_text, sched_text]
        for col, value in enumerate(values):
            item = _JobsSortItem(value)
            if col == 2:
                item.setData(Qt.ItemDataRole.UserRole, status_rank.get(status, 0))
            elif col == 3:
                item.setData(Qt.ItemDataRole.UserRole, last_sort)
            if col == 2 and status == "Success":
                item.setForeground(Qt.GlobalColor.green)
            if col == 3 and last_run and last_run != "—":
                item.setToolTip(str(last_run))
            if col == 4 and snap_full:
                item.setToolTip(str(snap_full))
            table.setItem(row, col, item)
    table.setSortingEnabled(was_sorting)
    if was_sorting:
        table.sortItems(sort_col, sort_order)
        header.setSortIndicator(sort_col, sort_order)
