"""Modern restore files page builder."""
from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.cards import SectionCard
from ui.table_helpers import TableRowHover

_LABEL_W = 96
_ACTION_W = 128
_DATE_W = 168


def _secondary_btn(text: str, slot, *, tooltip: str = "") -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("dialogSecondary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(34)
    btn.setFixedWidth(_ACTION_W)
    if tooltip:
        btn.setToolTip(tooltip)
    btn.clicked.connect(slot)
    return btn


def _row(
    label: str,
    field: QWidget,
    action: Optional[QWidget] = None,
    *,
    compact_field: bool = False,
) -> QWidget:
    """One restore form row: label | field | fixed action column."""
    wrap = QWidget()
    wrap.setObjectName("restoreFormRow")
    row = QHBoxLayout(wrap)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)

    lab = QLabel(label)
    lab.setObjectName("restoreFormLabel")
    lab.setFixedWidth(_LABEL_W)
    lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(lab, 0)

    if compact_field:
        row.addWidget(field, 0)
        row.addStretch(1)
    else:
        row.addWidget(field, stretch=1)

    if action is not None:
        row.addWidget(action, 0)
    else:
        spacer = QWidget()
        spacer.setFixedWidth(_ACTION_W)
        row.addWidget(spacer, 0)
    return wrap


def create_restore_page(host: Any) -> QWidget:
    """Build the restore files page and attach widgets onto ``host``."""
    page = QWidget()
    page.setVisible(False)
    page.setObjectName("restorePage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(16)

    # Header (same pattern as Snapshots / Repositories)
    header = QHBoxLayout()
    header.setSpacing(12)
    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Restore Files")
    title.setObjectName("pageTitle")
    title_col.addWidget(title)
    subtitle = QLabel(
        "Pick a snapshot, choose what to restore, and send it to a folder or the original path."
    )
    subtitle.setObjectName("pageSubtitle")
    title_col.addWidget(subtitle)
    header.addLayout(title_col, stretch=1)

    host.mount_browse_btn = QPushButton("Browse Files")
    host.mount_browse_btn.setObjectName("dialogSecondary")
    host.mount_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    host.mount_browse_btn.setMinimumHeight(34)
    host.mount_browse_btn.setToolTip(
        "Browse all snapshots in the repository and restore specific files"
    )
    host.mount_browse_btn.clicked.connect(host.mount_and_browse_snapshot)
    header.addWidget(host.mount_browse_btn, 0)

    restore_btn = QPushButton("Start Restore")
    restore_btn.setObjectName("dialogPrimary")
    restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    restore_btn.setMinimumHeight(34)
    restore_btn.clicked.connect(host.start_restore)
    header.addWidget(restore_btn, 0)
    layout.addLayout(header)

    # ── Configuration card ──────────────────────────────────────────
    config_card = SectionCard("Restore Configuration", parent=page)
    config_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    fields = QVBoxLayout()
    fields.setContentsMargins(0, 0, 0, 0)
    fields.setSpacing(10)

    host.restore_repo_combo = QComboBox()
    host.restore_repo_combo.setMinimumHeight(34)
    host.restore_repo_combo.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    host.restore_repo_combo.currentTextChanged.connect(host.load_snapshots_for_restore)
    fields.addWidget(_row("Repository", host.restore_repo_combo))

    host.restore_snapshot_combo = QComboBox()
    host.restore_snapshot_combo.setMinimumHeight(34)
    host.restore_snapshot_combo.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    latest_btn = _secondary_btn(
        "Latest",
        host.select_latest_snapshot,
        tooltip="Jump to the most recent snapshot",
    )
    fields.addWidget(_row("Snapshot", host.restore_snapshot_combo, latest_btn))

    host.restore_date_edit = QDateEdit()
    host.restore_date_edit.setObjectName("restoreDateEdit")
    host.restore_date_edit.setDate(QDate.currentDate())
    host.restore_date_edit.setCalendarPopup(True)
    host.restore_date_edit.setDisplayFormat("dd/MM/yyyy")
    host.restore_date_edit.setMinimumHeight(34)
    host.restore_date_edit.setFixedWidth(_DATE_W)
    find_date_btn = _secondary_btn(
        "Find Snapshot",
        host.find_snapshot_by_date,
        tooltip="Find snapshot closest to selected date",
    )
    fields.addWidget(
        _row("Quick date", host.restore_date_edit, find_date_btn, compact_field=True)
    )

    host.restore_path_input = QLineEdit()
    host.restore_path_input.setPlaceholderText("Leave empty to restore all files")
    host.restore_path_input.setMinimumHeight(34)
    browse_snap_btn = _secondary_btn(
        "Browse Snapshot",
        host.browse_snapshot_files,
        tooltip="Browse files in the selected snapshot",
    )
    fields.addWidget(_row("Path", host.restore_path_input, browse_snap_btn))

    # Destination block (full card width)
    dest_wrap = QFrame()
    dest_wrap.setObjectName("restoreDestStrip")
    dest_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    dest_layout = QVBoxLayout(dest_wrap)
    dest_layout.setContentsMargins(12, 10, 12, 10)
    dest_layout.setSpacing(10)

    host.restore_to_original_check = QCheckBox("Restore to original location")
    host.restore_to_original_check.setToolTip(
        "When checked, files will be restored to their original paths from the snapshot"
    )
    host.restore_to_original_check.setCursor(Qt.CursorShape.PointingHandCursor)
    host.restore_to_original_check.stateChanged.connect(host._on_restore_to_original_changed)
    dest_layout.addWidget(host.restore_to_original_check)

    host.restore_target_input = QLineEdit()
    host.restore_target_input.setPlaceholderText("Select target directory for restore")
    host.restore_target_input.setMinimumHeight(34)
    host.restore_target_input.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    host.target_browse_btn = _secondary_btn(
        "Browse",
        host.browse_restore_target,
        tooltip="Choose restore destination folder",
    )
    dest_layout.addWidget(_row("Restore to", host.restore_target_input, host.target_browse_btn))
    fields.addWidget(dest_wrap)

    config_card.body.addLayout(fields)
    layout.addWidget(config_card, stretch=0)

    host.restore_progress = QProgressBar()
    host.restore_progress.setVisible(False)
    host.restore_progress.setTextVisible(False)
    host.restore_progress.setMinimumHeight(8)
    layout.addWidget(host.restore_progress)

    # ── Search card ─────────────────────────────────────────────────
    search_card = SectionCard("Search Across All Snapshots", parent=page)
    search_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    search_row = QHBoxLayout()
    search_row.setSpacing(8)
    host.global_search_input = QLineEdit()
    host.global_search_input.setPlaceholderText(
        "Filename or path pattern (e.g. *.pdf, document.txt, /path/to/folder)"
    )
    host.global_search_input.setMinimumHeight(34)
    host.global_search_input.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    search_row.addWidget(host.global_search_input, stretch=1)
    search_btn = _secondary_btn(
        "Search",
        host.search_across_snapshots,
        tooltip="Search every snapshot in the selected repository",
    )
    search_row.addWidget(search_btn)
    search_card.body.addLayout(search_row)

    host.search_results_table = QTableWidget()
    host.search_results_table.setObjectName("restoreSearchTable")
    host.search_results_table.setColumnCount(6)
    host.search_results_table.setHorizontalHeaderLabels(
        ["File/Folder", "Path", "Snapshot ID", "Date/Time", "Size", "Action"]
    )
    results_header = host.search_results_table.horizontalHeader()
    results_header.setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter
    )
    results_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    results_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    results_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    results_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    results_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    results_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
    host.search_results_table.setColumnWidth(5, 100)
    host.search_results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    host.search_results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    host.search_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    host.search_results_table.setAlternatingRowColors(False)
    host.search_results_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    host.search_results_table.verticalHeader().setVisible(False)
    host.search_results_table.setShowGrid(False)
    host.search_results_table.setWordWrap(False)
    host.search_results_table.verticalHeader().setDefaultSectionSize(44)
    host.search_results_table.setMinimumHeight(160)
    host.search_results_table.setMaximumHeight(240)
    host.search_results_table.setMouseTracking(True)
    host.search_results_table.viewport().setMouseTracking(True)
    host._restore_search_hover = TableRowHover(
        host.search_results_table,
        nudge_foreground=True,
        paint_background=False,
        lighten_amount=0.08,
    )
    host.search_results_table.setVisible(False)

    results_shell = QFrame()
    results_shell.setObjectName("restoreSearchTableShell")
    results_shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    results_shell.setVisible(False)
    host._restore_results_shell = results_shell
    shell_layout = QVBoxLayout(results_shell)
    shell_layout.setContentsMargins(0, 0, 0, 0)
    shell_layout.setSpacing(0)
    shell_layout.addWidget(host.search_results_table)
    search_card.body.addWidget(results_shell)
    layout.addWidget(search_card, stretch=0)

    _orig_set_visible = host.search_results_table.setVisible

    def _set_results_visible(visible: bool, _orig=_orig_set_visible, shell=results_shell) -> None:
        _orig(visible)
        shell.setVisible(visible)

    host.search_results_table.setVisible = _set_results_visible  # type: ignore[method-assign]

    # ── Log card ────────────────────────────────────────────────────
    log_card = QFrame(page)
    log_card.setObjectName("sectionCard")
    log_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    log_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    log_layout = QVBoxLayout(log_card)
    log_layout.setContentsMargins(16, 14, 16, 14)
    log_layout.setSpacing(10)

    log_title = QLabel("Restore Log", log_card)
    log_title.setObjectName("sectionCardTitle")
    log_layout.addWidget(log_title, 0)

    host.restore_log = QPlainTextEdit(log_card)
    host.restore_log.setObjectName("restoreLog")
    host.restore_log.setReadOnly(True)
    host.restore_log.setPlaceholderText("Restore output will appear here…")
    host.restore_log.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    log_layout.addWidget(host.restore_log, 1)
    layout.addWidget(log_card, stretch=1)

    return page
