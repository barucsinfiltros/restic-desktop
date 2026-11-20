"""Modern restore files page builder."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QButtonGroup,
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
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.cards import SectionCard
from ui.table_helpers import TableRowHover

_LABEL_W = 96
_ACTION_W = 128
_DATE_W = 168

_RESTORE_SUBTITLE = (
    "Pick a snapshot, choose what to restore, and send it to a folder "
    "or the original path."
)
_FIND_SUBTITLE = (
    "Search every snapshot in the selected repository for a file or folder, "
    "then restore a match."
)


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


def _mode_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("restoreModeBtn")
    btn.setCheckable(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(32)
    btn.setMinimumWidth(110)
    return btn


def create_restore_page(host: Any) -> QWidget:
    """Build the restore files page and attach widgets onto ``host``."""
    page = QWidget()
    page.setVisible(False)
    page.setObjectName("restorePage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(14)

    # Header
    header = QHBoxLayout()
    header.setSpacing(12)
    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Restore Files")
    title.setObjectName("pageTitle")
    title_col.addWidget(title)
    host.restore_page_subtitle = QLabel(_RESTORE_SUBTITLE)
    host.restore_page_subtitle.setObjectName("pageSubtitle")
    host.restore_page_subtitle.setWordWrap(True)
    title_col.addWidget(host.restore_page_subtitle)
    header.addLayout(title_col, stretch=1)
    layout.addLayout(header)

    # Mode switcher
    mode_bar = QFrame(page)
    mode_bar.setObjectName("restoreModeBar")
    mode_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    mode_row = QHBoxLayout(mode_bar)
    mode_row.setContentsMargins(4, 4, 4, 4)
    mode_row.setSpacing(4)

    host.restore_mode_btn = _mode_button("Restore")
    host.find_files_mode_btn = _mode_button("Find files")
    host.restore_mode_btn.setChecked(True)
    host.restore_mode_group = QButtonGroup(page)
    host.restore_mode_group.setExclusive(True)
    host.restore_mode_group.addButton(host.restore_mode_btn, 0)
    host.restore_mode_group.addButton(host.find_files_mode_btn, 1)
    mode_row.addWidget(host.restore_mode_btn)
    mode_row.addWidget(host.find_files_mode_btn)
    mode_row.addStretch(1)
    layout.addWidget(mode_bar, 0, Qt.AlignmentFlag.AlignLeft)

    # Shared repository (both modes need it)
    repo_strip = QFrame(page)
    repo_strip.setObjectName("restoreRepoStrip")
    repo_strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    repo_strip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    repo_strip_layout = QVBoxLayout(repo_strip)
    repo_strip_layout.setContentsMargins(14, 12, 14, 12)
    repo_strip_layout.setSpacing(0)
    host.restore_repo_combo = QComboBox()
    host.restore_repo_combo.setMinimumHeight(34)
    host.restore_repo_combo.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    host.restore_repo_combo.currentTextChanged.connect(host.load_snapshots_for_restore)
    repo_strip_layout.addWidget(_row("Repository", host.restore_repo_combo))
    layout.addWidget(repo_strip, 0)

    host.restore_mode_stack = QStackedWidget(page)
    host.restore_mode_stack.setObjectName("restoreModeStack")
    layout.addWidget(host.restore_mode_stack, stretch=1)

    # ── Restore mode ────────────────────────────────────────────────
    restore_pane = QWidget()
    restore_layout = QVBoxLayout(restore_pane)
    restore_layout.setContentsMargins(0, 0, 0, 0)
    restore_layout.setSpacing(14)

    config_card = SectionCard("Restore Configuration", parent=restore_pane)
    config_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    fields = QVBoxLayout()
    fields.setContentsMargins(0, 0, 0, 0)
    fields.setSpacing(10)

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

    dest_wrap = QFrame()
    dest_wrap.setObjectName("restoreDestStrip")
    dest_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    dest_layout = QVBoxLayout(dest_wrap)
    dest_layout.setContentsMargins(12, 10, 12, 10)
    dest_layout.setSpacing(10)

    host.restore_to_original_check = QCheckBox("Restore to original location")
    host.restore_to_original_check.setEnabled(False)
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
    dest_layout.addWidget(
        _row("Restore to", host.restore_target_input, host.target_browse_btn)
    )
    fields.addWidget(dest_wrap)

    config_card.body.addLayout(fields)
    restore_layout.addWidget(config_card, stretch=0)

    host.restore_progress = QProgressBar()
    host.restore_progress.setVisible(False)
    host.restore_progress.setTextVisible(False)
    host.restore_progress.setMinimumHeight(8)
    restore_layout.addWidget(host.restore_progress)

    log_card = QFrame(restore_pane)
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
    restore_layout.addWidget(log_card, stretch=1)

    host.restore_mode_stack.addWidget(restore_pane)

    # ── Find files mode ─────────────────────────────────────────────
    find_pane = QWidget()
    find_layout = QVBoxLayout(find_pane)
    find_layout.setContentsMargins(0, 0, 0, 0)
    find_layout.setSpacing(14)

    search_card = SectionCard("Search Across Snapshots", parent=find_pane)
    search_card.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )

    search_hint = QLabel(
        "Uses the repository selected above. Patterns like *.pdf or a folder path work."
    )
    search_hint.setObjectName("pageSubtitle")
    search_hint.setWordWrap(True)
    search_card.body.addWidget(search_hint)

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
    host.global_search_input.returnPressed.connect(host.search_across_snapshots)
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
    host.search_results_table.setSelectionBehavior(
        QTableWidget.SelectionBehavior.SelectRows
    )
    host.search_results_table.setSelectionMode(
        QTableWidget.SelectionMode.SingleSelection
    )
    host.search_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    host.search_results_table.setAlternatingRowColors(False)
    host.search_results_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    host.search_results_table.verticalHeader().setVisible(False)
    host.search_results_table.setShowGrid(False)
    host.search_results_table.setWordWrap(False)
    host.search_results_table.verticalHeader().setDefaultSectionSize(44)
    host.search_results_table.setMinimumHeight(200)
    host.search_results_table.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
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
    results_shell.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    host._restore_results_shell = results_shell
    shell_layout = QVBoxLayout(results_shell)
    shell_layout.setContentsMargins(0, 0, 0, 0)
    shell_layout.setSpacing(0)
    shell_layout.addWidget(host.search_results_table)
    search_card.body.addWidget(results_shell, stretch=1)

    host._restore_search_empty = QLabel(
        "Search results will appear here.",
        search_card,
    )
    host._restore_search_empty.setObjectName("pageSubtitle")
    host._restore_search_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
    host._restore_search_empty.setMinimumHeight(120)
    search_card.body.addWidget(host._restore_search_empty, stretch=1)

    find_layout.addWidget(search_card, stretch=1)
    host.restore_mode_stack.addWidget(find_pane)

    _orig_set_visible = host.search_results_table.setVisible

    def _set_results_visible(
        visible: bool,
        _orig=_orig_set_visible,
        shell=results_shell,
        empty=host._restore_search_empty,
    ) -> None:
        _orig(visible)
        shell.setVisible(visible)
        empty.setVisible(not visible)

    host.search_results_table.setVisible = _set_results_visible  # type: ignore[method-assign]

    def _switch_restore_mode(index: int) -> None:
        host.restore_mode_stack.setCurrentIndex(index)
        if index == 1:
            host.restore_page_subtitle.setText(_FIND_SUBTITLE)
        else:
            host.restore_page_subtitle.setText(_RESTORE_SUBTITLE)

    host.restore_mode_group.idClicked.connect(_switch_restore_mode)
    host._switch_restore_mode = _switch_restore_mode

    return page
