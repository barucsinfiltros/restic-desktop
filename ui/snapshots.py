"""Modern snapshots page builder."""
from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.rounded_menu import RoundedMenu
from ui.cards import SectionCard
from ui.dashboard import _parse_timestamp, format_relative_time_short
from ui.icons import tinted_icon
from ui.table_helpers import (
    SortableTableItem,
    TableRowHover,
    make_snapshot_id_cell,
    make_snapshot_size_cell,
)

import ui.themes as themes

# Columns: ID, Time, Host, Tags, Paths, Size, menu
_COL_ID = 0
_COL_TIME = 1
_COL_HOST = 2
_COL_TAGS = 3
_COL_PATHS = 4
_COL_SIZE = 5
_COL_MENU = 6


def snapshot_data_from_row(table: QTableWidget, row: int) -> Optional[dict]:
    """Return full snapshot dict stored on the ID column item."""
    item = table.item(row, _COL_ID)
    if item is None:
        return None
    data = item.data(Qt.ItemDataRole.UserRole)
    return data if isinstance(data, dict) else None


def snapshot_short_id_from_row(table: QTableWidget, row: int) -> str:
    """Short snapshot id for display / restic CLI (from stored snapshot dict)."""
    data = snapshot_data_from_row(table, row)
    if data:
        sid = data.get("short_id") or data.get("id", "")
        return str(sid)[:8] if sid else ""
    item = table.item(row, _COL_ID)
    return item.text() if item else ""


def snapshot_previous_short_id(snapshots: list[dict], current: dict) -> str:
    """Return the short id of the snapshot immediately before ``current`` in time."""
    if not snapshots or not current:
        return ""

    def _time_key(s: dict) -> float:
        return float(_snapshot_sort_key(s, _COL_TIME))

    ordered = sorted(snapshots, key=_time_key)
    cur_id = current.get("short_id") or str(current.get("id", ""))[:8]
    cur_full = current.get("id", "")
    idx = -1
    for i, snap in enumerate(ordered):
        sid = snap.get("short_id") or str(snap.get("id", ""))[:8]
        if sid == cur_id or (cur_full and snap.get("id") == cur_full):
            idx = i
            break
    if idx <= 0:
        return ""
    prev = ordered[idx - 1]
    return str(prev.get("short_id") or str(prev.get("id", ""))[:8])


def create_snapshots_page(host: Any) -> QWidget:
    """Build the snapshots browser page and attach widgets onto ``host``."""
    page = QWidget()
    page.setVisible(False)
    page.setObjectName("snapshotsPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(16)

    # Header
    header = QHBoxLayout()
    header.setSpacing(12)
    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Snapshots")
    title.setObjectName("pageTitle")
    title_col.addWidget(title)
    subtitle = QLabel("Browse and manage snapshots in a selected repository.")
    subtitle.setObjectName("pageSubtitle")
    title_col.addWidget(subtitle)
    header.addLayout(title_col, stretch=1)

    repo_row = QHBoxLayout()
    repo_row.setSpacing(8)
    repo_label = QLabel("Repository")
    repo_label.setObjectName("pageSubtitle")
    repo_row.addWidget(repo_label)
    host.snapshot_repo_combo = QComboBox()
    host.snapshot_repo_combo.setMinimumWidth(220)
    host.snapshot_repo_combo.setMinimumHeight(32)
    host.snapshot_repo_combo.currentTextChanged.connect(host.load_snapshots)
    repo_row.addWidget(host.snapshot_repo_combo)
    header.addLayout(repo_row, 0)
    layout.addLayout(header)

    # Snapshots table card
    table_card = SectionCard("Snapshots", parent=page)
    table_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # Compact summary strip (count / latest / data added)
    summary = QFrame()
    summary.setObjectName("snapshotSummaryStrip")
    summary.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    summary_row = QHBoxLayout(summary)
    summary_row.setContentsMargins(14, 10, 14, 10)
    summary_row.setSpacing(16)

    def _summary_metric(label: str) -> QLabel:
        col = QVBoxLayout()
        col.setSpacing(2)
        lab = QLabel(label)
        lab.setObjectName("snapshotSummaryLabel")
        val = QLabel("—")
        val.setObjectName("snapshotSummaryValue")
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(lab)
        col.addWidget(val)
        summary_row.addLayout(col, stretch=1)
        return val

    def _summary_divider() -> None:
        line = QFrame()
        line.setObjectName("snapshotSummaryDivider")
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedWidth(1)
        line.setFixedHeight(28)
        summary_row.addWidget(line, 0, Qt.AlignmentFlag.AlignVCenter)

    host.snapshot_summary_count = _summary_metric("Snapshots")
    _summary_divider()
    host.snapshot_summary_latest = _summary_metric("Latest")
    _summary_divider()
    host.snapshot_summary_size = _summary_metric("Data added")
    table_card.body.addWidget(summary)

    host.snapshots_table = QTableWidget()
    host.snapshots_table.setObjectName("snapshotsTable")
    host.snapshots_table.setColumnCount(7)
    host.snapshots_table.setHorizontalHeaderLabels(
        ["ID", "Time", "Host", "Tags", "Paths", "Size", ""]
    )
    snap_header = host.snapshots_table.horizontalHeader()
    snap_header.setStretchLastSection(False)
    snap_header.setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter
    )
    snap_header.setSectionResizeMode(_COL_ID, QHeaderView.ResizeMode.ResizeToContents)
    snap_header.setSectionResizeMode(_COL_TIME, QHeaderView.ResizeMode.ResizeToContents)
    snap_header.setSectionResizeMode(_COL_HOST, QHeaderView.ResizeMode.ResizeToContents)
    snap_header.setSectionResizeMode(_COL_TAGS, QHeaderView.ResizeMode.ResizeToContents)
    snap_header.setSectionResizeMode(_COL_PATHS, QHeaderView.ResizeMode.Stretch)
    snap_header.setSectionResizeMode(_COL_SIZE, QHeaderView.ResizeMode.Fixed)
    snap_header.setSectionResizeMode(_COL_MENU, QHeaderView.ResizeMode.Fixed)
    host.snapshots_table.setColumnWidth(_COL_SIZE, 168)
    host.snapshots_table.setColumnWidth(_COL_MENU, 52)
    snap_header.setSectionsClickable(True)
    snap_header.setSortIndicatorShown(True)
    snap_header.setSortIndicator(_COL_TIME, Qt.SortOrder.DescendingOrder)
    host.snapshots_table.setSortingEnabled(False)
    host.snapshots_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    host.snapshots_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    host.snapshots_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    host.snapshots_table.setAlternatingRowColors(False)
    host.snapshots_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    host.snapshots_table.verticalHeader().setVisible(False)
    host.snapshots_table.setShowGrid(False)
    host.snapshots_table.setWordWrap(False)
    host.snapshots_table.setTextElideMode(Qt.TextElideMode.ElideNone)
    host.snapshots_table.setMinimumHeight(180)
    host.snapshots_table.verticalHeader().setDefaultSectionSize(48)
    host.snapshots_table.setMouseTracking(True)
    host.snapshots_table.viewport().setMouseTracking(True)
    host._snapshots_table_hover = TableRowHover(
        host.snapshots_table,
        nudge_foreground=True,
        paint_background=False,
        lighten_amount=0.08,
    )
    host.snapshots_table.itemSelectionChanged.connect(host.show_snapshot_details)

    table_shell = QFrame()
    table_shell.setObjectName("snapshotsTableShell")
    table_shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    shell_layout = QVBoxLayout(table_shell)
    shell_layout.setContentsMargins(0, 0, 0, 0)
    shell_layout.setSpacing(0)
    shell_layout.addWidget(host.snapshots_table)
    table_card.body.addWidget(table_shell, stretch=1)

    def _resort(column: int) -> None:
        if column >= _COL_MENU:
            return
        header = host.snapshots_table.horizontalHeader()
        if header.sortIndicatorSection() == column:
            new_order = (
                Qt.SortOrder.AscendingOrder
                if header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
                else Qt.SortOrder.DescendingOrder
            )
        else:
            new_order = Qt.SortOrder.DescendingOrder if column == _COL_TIME else Qt.SortOrder.AscendingOrder
        header.setSortIndicator(column, new_order)
        populate_snapshots_table(host)

    snap_header.sectionClicked.connect(_resort)

    # Repository-level actions stay outside the row menu.
    repo_actions = QHBoxLayout()
    repo_actions.setSpacing(8)
    repo_actions.setContentsMargins(0, 4, 0, 0)
    repo_actions.addStretch(1)

    def _repo_action(label: str, slot) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("linkBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        repo_actions.addWidget(btn)
        return btn

    _repo_action("Prune Repository", host.prune_repository)
    _repo_action("Unlock Repository", host.unlock_repository)
    table_card.body.addLayout(repo_actions)
    # Stretch the table shell (index 2: header, summary, table, actions)
    table_card.body.setStretch(2, 1)

    layout.addWidget(table_card, stretch=2)

    # Details card
    details_card = QFrame(page)
    details_card.setObjectName("sectionCard")
    details_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    details_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    details_layout = QVBoxLayout(details_card)
    details_layout.setContentsMargins(16, 14, 16, 14)
    details_layout.setSpacing(10)

    details_title = QLabel("Snapshot Details", details_card)
    details_title.setObjectName("sectionCardTitle")
    details_layout.addWidget(details_title, 0)

    host.snapshot_details = QTextEdit(details_card)
    host.snapshot_details.setObjectName("snapshotDetails")
    host.snapshot_details.setReadOnly(True)
    host.snapshot_details.setFont(QFont("Consolas", 10))
    host.snapshot_details.setPlaceholderText("Select a snapshot to view details…")
    host.snapshot_details.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    host.snapshot_details.setMinimumHeight(0)
    host.snapshot_details.setMaximumHeight(16777215)
    details_layout.addWidget(host.snapshot_details, 1)

    layout.addWidget(details_card, stretch=1)

    host.refresh_snapshots_table = lambda: populate_snapshots_table(host)

    return page


def _snapshot_sort_key(snapshot: dict, column: int):
    if column == _COL_ID:
        sid = snapshot.get("short_id") or snapshot.get("id", "")
        return str(sid).lower()
    if column == _COL_TIME:
        raw = snapshot.get("time", "") or ""
        parsed = _parse_timestamp(str(raw))
        return parsed.timestamp() if parsed is not None else 0.0
    if column == _COL_HOST:
        return (snapshot.get("hostname") or "").lower()
    if column == _COL_TAGS:
        return ", ".join(snapshot.get("tags") or []).lower()
    if column == _COL_PATHS:
        return "\n".join(snapshot.get("paths") or []).lower()
    if column == _COL_SIZE:
        summary = snapshot.get("summary") or {}
        try:
            return int(summary.get("data_added") or 0)
        except (TypeError, ValueError):
            return 0
    return ""


def _format_snapshot_time(raw: str) -> str:
    if not raw:
        return "—"
    return str(raw).replace("T", " ").split(".")[0].replace("Z", "")


def _latest_summary_label(raw_time: str) -> tuple[str, str]:
    """Return (display, tooltip) for the Latest summary metric."""
    if not raw_time:
        return "—", ""
    parsed = _parse_timestamp(str(raw_time))
    absolute = _format_snapshot_time(raw_time)
    if parsed is None:
        return absolute or "—", absolute

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local_now = now.astimezone()
    local_dt = parsed.astimezone()
    if local_dt.date() == local_now.date():
        return "Today", absolute
    if (local_now.date() - local_dt.date()).days == 1:
        return "Yesterday", absolute
    return format_relative_time_short(str(raw_time)), absolute


def update_snapshots_summary(host: Any, snapshots: list[dict] | None = None) -> None:
    """Refresh the compact summary strip above the snapshots table."""
    count_lbl = getattr(host, "snapshot_summary_count", None)
    latest_lbl = getattr(host, "snapshot_summary_latest", None)
    size_lbl = getattr(host, "snapshot_summary_size", None)
    if count_lbl is None or latest_lbl is None or size_lbl is None:
        return

    snaps = list(snapshots if snapshots is not None else getattr(host, "_loaded_snapshots", None) or [])
    count = len(snaps)
    count_lbl.setText(str(count) if count else "0")

    latest_raw = ""
    total_added = 0
    for snap in snaps:
        raw = snap.get("time") or ""
        if raw and (not latest_raw or str(raw) > str(latest_raw)):
            latest_raw = str(raw)
        summary = snap.get("summary") or {}
        try:
            total_added += int(summary.get("data_added") or 0)
        except (TypeError, ValueError):
            pass

    latest_text, latest_tip = _latest_summary_label(latest_raw)
    latest_lbl.setText(latest_text)
    latest_lbl.setToolTip(latest_tip)

    format_bytes = getattr(host, "format_bytes", None)
    if total_added > 0 and callable(format_bytes):
        size_lbl.setText(format_bytes(total_added))
    elif total_added > 0:
        size_lbl.setText(str(total_added))
    else:
        size_lbl.setText("—")
    size_lbl.setToolTip(
        "Sum of data added by these snapshots (not unique repository storage)"
        if total_added > 0
        else ""
    )


def _make_snapshot_menu_cell(
    host: Any,
    row: int,
    *,
    icon_color: str,
    on_browse: Callable[[], None],
    on_diff: Callable[[], None],
    on_copy: Callable[[], None],
    on_forget: Callable[[], None],
    parent=None,
) -> QWidget:
    """Kebab (⋯) button for per-snapshot actions."""
    cell = QWidget(parent)
    cell.setObjectName("snapshotActions")
    row_layout = QHBoxLayout(cell)
    row_layout.setContentsMargins(0, 0, 8, 0)
    row_layout.setSpacing(0)
    row_layout.addStretch(1)

    btn = QPushButton(cell)
    btn.setObjectName("iconMenuBtn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Snapshot actions")
    btn.setFlat(True)
    btn.setFixedSize(32, 32)
    btn.setIcon(tinted_icon("more_horiz.svg", icon_color, 18))
    btn.setIconSize(QSize(18, 18))

    def _select_row() -> None:
        table = host.snapshots_table
        table.selectRow(row)
        host.show_snapshot_details()

    def _open_menu(_checked: bool = False, button: QPushButton = btn) -> None:
        menu = RoundedMenu(button)
        browse_act = menu.addAction("Browse content")
        diff_act = menu.addAction("Diff with previous")
        copy_act = menu.addAction("Copy to repository")
        menu.addSeparator()
        forget_act = menu.addAction("Forget")
        chosen = menu.exec(button.mapToGlobal(button.rect().bottomRight()))
        if chosen is None:
            return
        _select_row()
        if chosen is browse_act:
            on_browse()
        elif chosen is diff_act:
            on_diff()
        elif chosen is copy_act:
            on_copy()
        elif chosen is forget_act:
            on_forget()

    btn.clicked.connect(_open_menu)
    row_layout.addWidget(btn)
    return cell


def populate_snapshots_table(host: Any) -> None:
    """Fill the snapshots table from ``host._loaded_snapshots`` cache."""
    table = getattr(host, "snapshots_table", None)
    if table is None:
        return

    snapshots = list(getattr(host, "_loaded_snapshots", None) or [])
    repo_name = getattr(host, "_current_snapshot_repo_name", "") or ""

    repositories = []
    if hasattr(host, "settings_manager"):
        repositories = list(host.settings_manager.get("repositories") or [])
        if themes.ensure_repo_colors(repositories):
            host.settings_manager.set("repositories", repositories)
            host.settings_manager.save_settings()

    repo_color = themes.repo_color_for_name(repo_name, repositories) if repo_name else "#5a8cc8"

    header = table.horizontalHeader()
    sort_col = header.sortIndicatorSection()
    sort_order = header.sortIndicatorOrder()
    if sort_col < 0:
        sort_col = _COL_TIME
        sort_order = Qt.SortOrder.DescendingOrder

    reverse = sort_order == Qt.SortOrder.DescendingOrder
    if sort_col < _COL_MENU:
        snapshots.sort(key=lambda s: _snapshot_sort_key(s, sort_col), reverse=reverse)

    hover = getattr(host, "_snapshots_table_hover", None)
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

    format_bytes = getattr(host, "format_bytes", None)
    max_size = 0
    for snap in snapshots:
        summary = snap.get("summary") or {}
        try:
            max_size = max(max_size, int(summary.get("data_added") or 0))
        except (TypeError, ValueError):
            pass

    track_color = themes.soft_hex_rgba(muted, 0.28)
    bar_color = themes.soft_hex_rgba(repo_color, 0.85)

    update_snapshots_summary(host, snapshots)

    table.setRowCount(len(snapshots))

    for row, snapshot in enumerate(snapshots):
        short_id = snapshot.get("short_id") or str(snapshot.get("id", ""))[:8]
        time_str = _format_snapshot_time(snapshot.get("time", ""))
        hostname = snapshot.get("hostname", "") or "—"
        tags = ", ".join(snapshot.get("tags") or []) or "—"
        paths = "\n".join(snapshot.get("paths") or []) or "—"
        summary = snapshot.get("summary") or {}
        try:
            size_sort = int(summary.get("data_added") or 0)
        except (TypeError, ValueError):
            size_sort = 0
        if callable(format_bytes) and size_sort > 0:
            size_str = format_bytes(size_sort)
        else:
            size_str = "—"
        size_ratio = (size_sort / max_size) if max_size > 0 and size_sort > 0 else 0.0

        time_sort = _snapshot_sort_key(snapshot, _COL_TIME)

        # Size text lives in the cell widget — keep item text empty to avoid ghosting.
        values = ["", time_str, hostname, tags, paths, "", ""]
        for col, value in enumerate(values):
            item = SortableTableItem(value)
            item.setTextAlignment(left)
            if col == _COL_ID:
                item.setData(Qt.ItemDataRole.UserRole, snapshot)
                item.setData(Qt.ItemDataRole.UserRole + 1, short_id.lower())
            elif col == _COL_TIME:
                item.setData(Qt.ItemDataRole.UserRole, time_sort)
            elif col == _COL_SIZE:
                item.setData(Qt.ItemDataRole.UserRole, size_sort)
            if col in (_COL_TIME, _COL_HOST, _COL_TAGS, _COL_PATHS):
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
            if col == _COL_PATHS and paths != "—":
                item.setToolTip(paths.replace("\n", "\n"))
            table.setItem(row, col, item)

        table.setCellWidget(
            row,
            _COL_ID,
            make_snapshot_id_cell(short_id, repo_color, parent=table),
        )
        table.setCellWidget(
            row,
            _COL_SIZE,
            make_snapshot_size_cell(
                size_str,
                ratio=size_ratio,
                bar_color=bar_color,
                track_color=track_color,
                text_color=muted,
                parent=table,
            ),
        )
        table.setCellWidget(
            row,
            _COL_MENU,
            _make_snapshot_menu_cell(
                host,
                row,
                icon_color=menu_icon,
                on_browse=host.browse_snapshot_content,
                on_diff=host.diff_snapshots,
                on_copy=host.copy_snapshot_to_repository,
                on_forget=host.forget_snapshot,
                parent=table,
            ),
        )
