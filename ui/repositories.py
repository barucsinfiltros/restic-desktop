"""Modern repositories page builder."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
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

from rounded_menu import RoundedMenu
from ui.cards import SectionCard
from ui.dashboard import _parse_timestamp
from ui.icons import tinted_icon
from ui.table_helpers import SortableTableItem, TableRowHover, make_repo_icon_cell

import themes

# Stale successful check → Warning (days)
_STALE_CHECK_DAYS = 7

# Columns: Name, Status, Path, Type, Last Checked, menu
_COL_NAME = 0
_COL_STATUS = 1
_COL_PATH = 2
_COL_TYPE = 3
_COL_CHECKED = 4
_COL_MENU = 5


def create_repositories_page(host: Any) -> QWidget:
    """Build the repositories page and attach widgets onto ``host``."""
    page = QWidget()
    page.setVisible(False)
    page.setObjectName("repositoriesPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(16)

    header = QHBoxLayout()
    header.setSpacing(12)
    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Repositories")
    title.setObjectName("pageTitle")
    title_col.addWidget(title)
    subtitle = QLabel("Manage backup repository connections and storage paths.")
    subtitle.setObjectName("pageSubtitle")
    title_col.addWidget(subtitle)
    header.addLayout(title_col, stretch=1)
    # Add Repository lives on the window title bar (same style as Refresh Dashboard).
    layout.addLayout(header)

    table_card = SectionCard("Configured Repositories", parent=page)
    table_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    host.repo_table = QTableWidget()
    host.repo_table.setObjectName("repoTable")
    host.repo_table.setColumnCount(6)
    host.repo_table.setHorizontalHeaderLabels(
        ["Name", "Status", "Path", "Type", "Last Checked", ""]
    )
    repo_header = host.repo_table.horizontalHeader()
    repo_header.setStretchLastSection(False)
    repo_header.setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter
    )
    repo_header.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.ResizeToContents)
    repo_header.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
    repo_header.setSectionResizeMode(_COL_PATH, QHeaderView.ResizeMode.Stretch)
    repo_header.setSectionResizeMode(_COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
    repo_header.setSectionResizeMode(_COL_CHECKED, QHeaderView.ResizeMode.ResizeToContents)
    repo_header.setSectionResizeMode(_COL_MENU, QHeaderView.ResizeMode.Fixed)
    host.repo_table.setColumnWidth(_COL_MENU, 52)
    repo_header.setSectionsClickable(True)
    repo_header.setSortIndicatorShown(True)
    repo_header.setSortIndicator(_COL_NAME, Qt.SortOrder.AscendingOrder)
    host.repo_table.setSortingEnabled(False)
    host.repo_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    host.repo_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    host.repo_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    host.repo_table.setAlternatingRowColors(False)
    host.repo_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    host.repo_table.verticalHeader().setVisible(False)
    host.repo_table.setShowGrid(False)
    host.repo_table.setWordWrap(False)
    host.repo_table.setTextElideMode(Qt.TextElideMode.ElideNone)
    host.repo_table.setMinimumHeight(200)
    host.repo_table.verticalHeader().setDefaultSectionSize(60)
    host.repo_table.setMouseTracking(True)
    host.repo_table.viewport().setMouseTracking(True)
    host._repo_table_hover = TableRowHover(
        host.repo_table,
        nudge_foreground=True,
        paint_background=False,
        lighten_amount=0.08,
    )

    table_shell = QFrame()
    table_shell.setObjectName("repoTableShell")
    table_shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    shell_layout = QVBoxLayout(table_shell)
    shell_layout.setContentsMargins(0, 0, 0, 0)
    shell_layout.setSpacing(0)
    shell_layout.addWidget(host.repo_table)
    table_card.body.addWidget(table_shell, stretch=1)
    layout.addWidget(table_card, stretch=1)

    def _resort(column: int) -> None:
        if column >= _COL_MENU:
            return
        header = host.repo_table.horizontalHeader()
        if header.sortIndicatorSection() == column:
            new_order = (
                Qt.SortOrder.AscendingOrder
                if header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
                else Qt.SortOrder.DescendingOrder
            )
        else:
            new_order = Qt.SortOrder.AscendingOrder
        header.setSortIndicator(column, new_order)
        populate_repository_table(
            host,
            on_edit=host.edit_repository_by_name,
            on_delete=host.delete_repository_by_name,
            on_check=getattr(host, "check_repository_by_name", None),
        )

    repo_header.sectionClicked.connect(_resort)

    return page


def resolve_repo_health(repo: dict) -> tuple[str, str, int]:
    """
    Return (status_key, label, sort_rank).

    status_key: healthy | warning | unreachable | unknown
    """
    raw = (repo.get("check_status") or "").strip().lower()
    if raw in ("ok", "success", "healthy"):
        raw = "healthy"
    elif raw in ("fail", "failed", "error", "unreachable"):
        raw = "unreachable"
    elif raw in ("warn", "warning", "stale"):
        raw = "warning"
    elif raw not in ("healthy", "warning", "unreachable", "unknown"):
        raw = "unknown"

    last = repo.get("last_checked") or ""
    if raw == "healthy" and last and last != "Never":
        parsed = _parse_timestamp(str(last))
        if parsed is not None:
            now = datetime.now(timezone.utc)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age_days = (now - parsed.astimezone(timezone.utc)).total_seconds() / 86400.0
            if age_days >= _STALE_CHECK_DAYS:
                raw = "warning"

    labels = {
        "healthy": "Healthy",
        "warning": "Warning",
        "unreachable": "Unreachable",
        "unknown": "Unknown",
    }
    ranks = {"healthy": 4, "warning": 3, "unreachable": 2, "unknown": 1}
    return raw, labels[raw], ranks[raw]


def _status_colors(app_theme) -> dict[str, str]:
    return {
        "healthy": getattr(app_theme, "ok", "#22c55e"),
        "warning": "#d97706",
        "unreachable": getattr(app_theme, "danger", "#ef4444"),
        "unknown": getattr(app_theme, "muted", "#8b95a5"),
    }


def make_repo_status_cell(
    status_key: str,
    label: str,
    color: str,
    *,
    tooltip: str = "",
    parent=None,
) -> QWidget:
    """Status label with coloured dot (avoids unicode bullet clipping)."""
    cell = QWidget(parent)
    cell.setObjectName("repoStatusCell")
    cell.setMinimumHeight(28)
    row = QHBoxLayout(cell)
    row.setContentsMargins(8, 4, 8, 4)
    row.setSpacing(8)

    dot = QLabel(cell)
    dot.setObjectName("repoStatusDot")
    dot.setFixedSize(8, 8)
    dot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    dot.setStyleSheet(
        f"QLabel#repoStatusDot {{"
        f"  background-color: {color};"
        f"  border: none;"
        f"  border-radius: 4px;"
        f"}}"
    )
    row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

    text = QLabel(label, cell)
    text.setObjectName("repoStatusLabel")
    text.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    text.setStyleSheet(
        f"QLabel#repoStatusLabel {{"
        f"  color: {color};"
        f"  background: transparent;"
        f"  border: none;"
        f"  font-size: 12px;"
        f"  padding: 0px;"
        f"  margin: 0px;"
        f"}}"
    )
    if tooltip:
        text.setToolTip(tooltip)
        dot.setToolTip(tooltip)
        cell.setToolTip(tooltip)
    row.addWidget(text, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addStretch(1)
    return cell


def _dot_icon(color_hex: str, *, size: int = 8) -> QIcon:
    """Create a tiny filled dot icon (avoids unicode bullet/layout clipping)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    pm.fill(QColor(color_hex))
    return QIcon(pm)


def _repo_sort_key(repo: dict, column: int):
    if column == _COL_NAME:
        return (repo.get("name") or "").lower()
    if column == _COL_STATUS:
        return resolve_repo_health(repo)[2]
    if column == _COL_PATH:
        return (repo.get("path") or "").lower()
    if column == _COL_TYPE:
        return (repo.get("type") or "").lower()
    if column == _COL_CHECKED:
        value = repo.get("last_checked") or ""
        if not value or value == "Never":
            return 0.0
        parsed = _parse_timestamp(str(value))
        return parsed.timestamp() if parsed is not None else 0.0
    return ""


def _make_repo_menu_cell(
    name: str,
    *,
    on_edit: Callable[[str], None],
    on_delete: Callable[[str], None],
    on_check: Optional[Callable[[str], None]],
    icon_color: str,
    parent=None,
) -> QWidget:
    """Kebab (⋯) button that opens Check / Edit / Delete."""
    cell = QWidget(parent)
    cell.setObjectName("repoActions")
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
        check_act = None
        if on_check is not None:
            check_act = menu.addAction("Check connection")
            menu.addSeparator()
        edit_act = menu.addAction("Edit")
        delete_act = menu.addAction("Delete")
        chosen = menu.exec(button.mapToGlobal(button.rect().bottomRight()))
        if check_act is not None and chosen is check_act and on_check is not None:
            on_check(name)
        elif chosen is edit_act:
            on_edit(name)
        elif chosen is delete_act:
            on_delete(name)

    btn.clicked.connect(_open_menu)
    row.addWidget(btn)
    return cell


def populate_repository_table(
    host: Any,
    *,
    on_edit: Callable[[str], None],
    on_delete: Callable[[str], None],
    on_check: Optional[Callable[[str], None]] = None,
) -> None:
    """Fill the repositories table from settings."""
    table = getattr(host, "repo_table", None)
    if table is None or not hasattr(host, "settings_manager"):
        return

    if on_check is None:
        on_check = getattr(host, "check_repository_by_name", None)

    repositories = list(host.settings_manager.get("repositories") or [])
    if themes.ensure_repo_colors(repositories):
        host.settings_manager.set("repositories", repositories)
        host.settings_manager.save_settings()

    header = table.horizontalHeader()
    sort_col = header.sortIndicatorSection()
    sort_order = header.sortIndicatorOrder()
    if sort_col < 0:
        sort_col = _COL_NAME
        sort_order = Qt.SortOrder.AscendingOrder

    reverse = sort_order == Qt.SortOrder.DescendingOrder
    if sort_col < _COL_MENU:
        repositories.sort(key=lambda r: _repo_sort_key(r, sort_col), reverse=reverse)

    hover = getattr(host, "_repo_table_hover", None)
    if hover is not None:
        hover._apply(-1)

    try:
        theme_id = themes.resolve_theme_id(host.settings_manager.get("theme"))
        app_theme = themes.get_app_theme(theme_id)
        muted = themes._mix_hex(app_theme.muted, app_theme.text, 0.18)
        menu_icon = app_theme.muted
        status_colors = _status_colors(app_theme)
    except Exception:
        muted = "#9aa3b2"
        menu_icon = "#8b95a5"
        status_colors = {
            "healthy": "#22c55e",
            "warning": "#d97706",
            "unreachable": "#ef4444",
            "unknown": "#8b95a5",
        }
    muted_color = QColor(muted)
    left = Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter

    table.setRowCount(len(repositories))

    for row, repo in enumerate(repositories):
        name = repo.get("name", "") or "—"
        path = repo.get("path", "") or "—"
        repo_type = repo.get("type", "local") or "local"
        last_checked = repo.get("last_checked", "Never") or "Never"
        last_sort = 0.0
        if last_checked and last_checked != "Never":
            parsed = _parse_timestamp(str(last_checked))
            if parsed is not None:
                last_sort = parsed.timestamp()

        status_key, status_label, status_rank = resolve_repo_health(repo)
        status_color = status_colors.get(status_key, muted)
        err = (repo.get("check_error") or "").strip()
        tip = err if status_key == "unreachable" and err else ""
        if status_key == "warning" and not tip:
            tip = f"Last successful check was over {_STALE_CHECK_DAYS} days ago"

        # Name/status display live in cell widgets — keep item text empty there.
        values = ["", status_label, path, repo_type, last_checked, ""]
        for col, value in enumerate(values):
            item = SortableTableItem(value)
            item.setTextAlignment(left)
            if col == _COL_NAME:
                item.setData(Qt.ItemDataRole.UserRole, name.lower())
            elif col == _COL_STATUS:
                item.setData(Qt.ItemDataRole.UserRole, status_rank)
                item.setForeground(QColor(status_color))
                item.setIcon(_dot_icon(status_color))
                item.setData(TableRowHover.BASE_FG_ROLE, status_color)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
                if tip:
                    item.setToolTip(tip)
            elif col == _COL_CHECKED:
                item.setData(Qt.ItemDataRole.UserRole, last_sort)
            if col in (_COL_PATH, _COL_TYPE, _COL_CHECKED):
                item.setForeground(muted_color)
                item.setData(TableRowHover.BASE_FG_ROLE, muted)
                item.setData(TableRowHover.HOVER_LIGHTEN_ROLE, True)
            if col == _COL_PATH:
                item.setToolTip(path)
            table.setItem(row, col, item)

        table.setCellWidget(
            row,
            _COL_NAME,
            make_repo_icon_cell(
                [name] if name and name != "—" else [],
                lambda n, repos=repositories: themes.repo_color_for_name(n, repos),
                parent=table,
            ),
        )
        table.setRowHeight(row, 60)
        table.setCellWidget(
            row,
            _COL_MENU,
            _make_repo_menu_cell(
                name,
                on_edit=on_edit,
                on_delete=on_delete,
                on_check=on_check,
                icon_color=menu_icon,
                parent=table,
            ),
        )

    # ResizeToContents ignores cell widgets (empty item text) — size Name for icon + label.
    table.resizeColumnToContents(_COL_NAME)
    table.setColumnWidth(_COL_NAME, max(table.columnWidth(_COL_NAME), 200))
    table.resizeColumnToContents(_COL_STATUS)
    table.setColumnWidth(_COL_STATUS, max(table.columnWidth(_COL_STATUS), 130))
    table.setColumnWidth(_COL_MENU, 52)

    header.setSortIndicator(sort_col, sort_order)
