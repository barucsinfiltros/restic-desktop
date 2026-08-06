"""Modern snapshots page builder."""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
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

from ui.cards import SectionCard
from ui.table_helpers import TableRowHover


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

    host.snapshots_table = QTableWidget()
    host.snapshots_table.setObjectName("snapshotsTable")
    host.snapshots_table.setColumnCount(6)
    host.snapshots_table.setHorizontalHeaderLabels(
        ["ID", "Time", "Host", "Tags", "Paths", "Size"]
    )
    snap_header = host.snapshots_table.horizontalHeader()
    snap_header.setStretchLastSection(False)
    snap_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    snap_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    snap_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    snap_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    snap_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    snap_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    host.snapshots_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    host.snapshots_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    host.snapshots_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    host.snapshots_table.setAlternatingRowColors(False)
    host.snapshots_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    host.snapshots_table.verticalHeader().setVisible(False)
    host.snapshots_table.setShowGrid(False)
    host.snapshots_table.setMinimumHeight(180)
    host.snapshots_table.verticalHeader().setDefaultSectionSize(40)
    host.snapshots_table.setMouseTracking(True)
    host.snapshots_table.viewport().setMouseTracking(True)
    host._snapshots_table_hover = TableRowHover(host.snapshots_table)
    host.snapshots_table.itemSelectionChanged.connect(host.show_snapshot_details)

    table_shell = QFrame()
    table_shell.setObjectName("snapshotsTableShell")
    table_shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    shell_layout = QVBoxLayout(table_shell)
    shell_layout.setContentsMargins(0, 0, 0, 0)
    shell_layout.setSpacing(0)
    shell_layout.addWidget(host.snapshots_table)
    table_card.body.addWidget(table_shell, stretch=1)

    # Compact action toolbar under the table
    actions = QHBoxLayout()
    actions.setSpacing(8)
    actions.setContentsMargins(0, 4, 0, 0)

    def _action(label: str, slot, *, danger: bool = False) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("dangerLinkBtn" if danger else "linkBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        actions.addWidget(btn)
        return btn

    _action("Browse Content", host.browse_snapshot_content)
    _action("Diff with Previous", host.diff_snapshots)
    _action("Copy to Repository", host.copy_snapshot_to_repository)
    _action("Forget", host.forget_snapshot, danger=True)
    actions.addStretch(1)
    _action("Prune Repository", host.prune_repository)
    _action("Unlock Repository", host.unlock_repository)
    table_card.body.addLayout(actions)
    table_card.body.setStretch(1, 1)  # table shell fills card

    layout.addWidget(table_card, stretch=2)

    # Details card built explicitly so the editor fills remaining height.
    # (SectionCard + QTextEdit stretch is unreliable under the global QTextEdit QSS.)
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

    return page
