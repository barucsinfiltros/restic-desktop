"""Modern repositories page builder."""
from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import Qt
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

from ui.cards import SectionCard
from ui.dashboard import _parse_timestamp
from ui.table_helpers import SortableTableItem, TableRowHover, make_repo_swatch_cell

import themes


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
    host.repo_table.setColumnCount(5)
    host.repo_table.setHorizontalHeaderLabels(
        ["Name", "Path", "Type", "Last Checked", "Actions"]
    )
    repo_header = host.repo_table.horizontalHeader()
    repo_header.setStretchLastSection(False)
    repo_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    repo_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    repo_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    repo_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    # Keep enough room for the Edit/Delete links (buttons are fixed width below).
    repo_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    host.repo_table.setColumnWidth(4, 170)
    repo_header.setSectionsClickable(True)
    repo_header.setSortIndicatorShown(True)
    repo_header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
    host.repo_table.setSortingEnabled(False)
    host.repo_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    host.repo_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    host.repo_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    host.repo_table.setAlternatingRowColors(False)
    host.repo_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    host.repo_table.verticalHeader().setVisible(False)
    host.repo_table.setShowGrid(False)
    host.repo_table.setMinimumHeight(200)
    host.repo_table.verticalHeader().setDefaultSectionSize(44)
    host.repo_table.setMouseTracking(True)
    host.repo_table.viewport().setMouseTracking(True)
    host._repo_table_hover = TableRowHover(host.repo_table)

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
        if column >= 4:
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
        )

    repo_header.sectionClicked.connect(_resort)

    return page


def _repo_sort_key(repo: dict, column: int):
    if column == 0:
        return (repo.get("name") or "").lower()
    if column == 1:
        return (repo.get("path") or "").lower()
    if column == 2:
        return (repo.get("type") or "local").lower()
    if column == 3:
        last_checked = repo.get("last_checked", "Never") or "Never"
        if last_checked == "Never":
            return 0.0
        parsed = _parse_timestamp(str(last_checked))
        return parsed.timestamp() if parsed is not None else 0.0
    return ""


def populate_repository_table(
    host: Any,
    *,
    on_edit: Callable[[str], None],
    on_delete: Callable[[str], None],
) -> None:
    """Fill the repositories table from settings."""
    table = getattr(host, "repo_table", None)
    if table is None or not hasattr(host, "settings_manager"):
        return

    repositories = list(host.settings_manager.get("repositories") or [])
    if themes.ensure_repo_colors(repositories):
        host.settings_manager.set("repositories", repositories)
        host.settings_manager.save_settings()

    header = table.horizontalHeader()
    sort_col = header.sortIndicatorSection()
    sort_order = header.sortIndicatorOrder()
    if sort_col < 0:
        sort_col = 0
        sort_order = Qt.SortOrder.AscendingOrder

    reverse = sort_order == Qt.SortOrder.DescendingOrder
    if sort_col < 4:
        repositories.sort(key=lambda r: _repo_sort_key(r, sort_col), reverse=reverse)

    hover = getattr(host, "_repo_table_hover", None)
    if hover is not None:
        hover._apply(-1)

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
        color = themes.repo_color_for_name(name, repositories)

        values = [name, path, repo_type, last_checked]
        for col, value in enumerate(values):
            item = SortableTableItem(value)
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, name.lower())
            elif col == 3:
                item.setData(Qt.ItemDataRole.UserRole, last_sort)
            if col == 1:
                item.setToolTip(path)
            table.setItem(row, col, item)

        table.setCellWidget(row, 0, make_repo_swatch_cell(name, color, parent=table))

        actions = QWidget(table)
        actions.setObjectName("repoActions")
        btn_row = QHBoxLayout(actions)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("linkBtn")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setFixedWidth(70)
        edit_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        edit_btn.clicked.connect(lambda _checked=False, n=name: on_edit(n))
        btn_row.addWidget(edit_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("dangerLinkBtn")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setFixedWidth(70)
        delete_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        delete_btn.clicked.connect(lambda _checked=False, n=name: on_delete(n))
        btn_row.addWidget(delete_btn)

        table.setCellWidget(row, 4, actions)

    header.setSortIndicator(sort_col, sort_order)
