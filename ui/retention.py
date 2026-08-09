"""Modern retention policy page builder."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ui.cards import SectionCard

_LABEL_W = 110
_FIELD_COMPACT_W = 160
_TIME_W = 128
_KEEP_SPIN_W = 88

_POLICY_SUBTITLE = (
    "Choose how many snapshots to keep, then dry-run or apply from the title bar."
)
_SCHEDULE_SUBTITLE = (
    "Run forget+prune automatically with a system task — independent of this app."
)


def _secondary_btn(
    text: str,
    slot,
    *,
    parent: Optional[QWidget] = None,
    tooltip: str = "",
    min_width: int = 0,
) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("dialogSecondary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(34)
    btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    if min_width:
        btn.setMinimumWidth(min_width)
    if tooltip:
        btn.setToolTip(tooltip)
    btn.clicked.connect(slot)
    return btn


def _form_row(
    label: str,
    field: QWidget,
    *,
    parent: Optional[QWidget] = None,
    compact: bool = False,
) -> QWidget:
    wrap = QWidget(parent)
    wrap.setObjectName("retentionFormRow")
    wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    row = QHBoxLayout(wrap)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)

    lab = QLabel(label, wrap)
    lab.setObjectName("retentionFormLabel")
    lab.setFixedWidth(_LABEL_W)
    lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(lab, 0)

    if compact:
        row.addWidget(field, 0)
        row.addStretch(1)
    else:
        row.addWidget(field, stretch=1)
    return wrap


def _setup_keep_spin(spin: QSpinBox, tip: str) -> None:
    spin.setObjectName("retentionKeepSpin")
    spin.setToolTip(tip)
    spin.setCursor(Qt.CursorShape.PointingHandCursor)
    spin.setFixedHeight(34)
    spin.setFixedWidth(_KEEP_SPIN_W)
    spin.setMinimum(0)
    spin.setAlignment(Qt.AlignmentFlag.AlignLeft)
    spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)


def _keep_field(
    title: str, spin: QSpinBox, tip: str, *, parent: Optional[QWidget] = None
) -> QWidget:
    """Label + compact spin — same label column as Repository / schedule rows."""
    wrap = QWidget(parent)
    wrap.setObjectName("retentionKeepField")
    wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    row = QHBoxLayout(wrap)
    row.setContentsMargins(0, 2, 8, 2)
    row.setSpacing(12)

    lab = QLabel(title, wrap)
    lab.setObjectName("retentionFormLabel")
    lab.setToolTip(tip)
    lab.setFixedWidth(_LABEL_W)
    lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(lab, 0)

    _setup_keep_spin(spin, tip)
    spin.setParent(wrap)
    row.addWidget(spin, 0)
    row.addStretch(1)
    return wrap


def _mode_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("restoreModeBtn")
    btn.setCheckable(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(32)
    btn.setMinimumWidth(110)
    return btn


def create_retention_page(host: Any) -> QWidget:
    """Build the retention policy page and attach widgets onto ``host``."""
    page = QWidget()
    page.setVisible(False)
    page.setObjectName("retentionPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(14)

    # Header (Dry Run / Apply live on the window title bar)
    header = QHBoxLayout()
    header.setSpacing(12)
    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Retention Policy", page)
    title.setObjectName("pageTitle")
    title_col.addWidget(title)
    host.retention_page_subtitle = QLabel(_POLICY_SUBTITLE, page)
    host.retention_page_subtitle.setObjectName("pageSubtitle")
    host.retention_page_subtitle.setWordWrap(True)
    title_col.addWidget(host.retention_page_subtitle)
    header.addLayout(title_col, stretch=1)
    layout.addLayout(header)

    # Mode switcher
    mode_bar = QFrame(page)
    mode_bar.setObjectName("restoreModeBar")
    mode_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    mode_row = QHBoxLayout(mode_bar)
    mode_row.setContentsMargins(4, 4, 4, 4)
    mode_row.setSpacing(4)

    host.retention_policy_mode_btn = _mode_button("Policy")
    host.retention_schedule_mode_btn = _mode_button("Schedule")
    host.retention_policy_mode_btn.setChecked(True)
    host.retention_mode_group = QButtonGroup(page)
    host.retention_mode_group.setExclusive(True)
    host.retention_mode_group.addButton(host.retention_policy_mode_btn, 0)
    host.retention_mode_group.addButton(host.retention_schedule_mode_btn, 1)
    mode_row.addWidget(host.retention_policy_mode_btn)
    mode_row.addWidget(host.retention_schedule_mode_btn)
    mode_row.addStretch(1)
    layout.addWidget(mode_bar, 0, Qt.AlignmentFlag.AlignLeft)

    # Shared repository
    repo_strip = QFrame(page)
    repo_strip.setObjectName("restoreRepoStrip")
    repo_strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    repo_strip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    repo_strip_layout = QVBoxLayout(repo_strip)
    repo_strip_layout.setContentsMargins(14, 12, 14, 12)
    repo_strip_layout.setSpacing(0)

    host.retention_repo_combo = QComboBox(repo_strip)
    host.retention_repo_combo.setMinimumHeight(34)
    host.retention_repo_combo.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    repo_strip_layout.addWidget(
        _form_row("Repository", host.retention_repo_combo, parent=repo_strip)
    )
    layout.addWidget(repo_strip, 0)

    host.retention_mode_stack = QStackedWidget(page)
    host.retention_mode_stack.setObjectName("restoreModeStack")
    layout.addWidget(host.retention_mode_stack, stretch=1)

    # ── Policy mode ─────────────────────────────────────────────────
    policy_pane = QWidget()
    policy_layout = QVBoxLayout(policy_pane)
    policy_layout.setContentsMargins(0, 0, 0, 0)
    policy_layout.setSpacing(14)

    config_card = SectionCard("Keep rules", parent=policy_pane)
    config_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    config_card.body.setContentsMargins(16, 14, 16, 16)
    config_card.body.setSpacing(12)

    host.keep_last_spin = QSpinBox()
    host.keep_last_spin.setMaximum(1000)
    host.keep_hourly_spin = QSpinBox()
    host.keep_hourly_spin.setMaximum(1000)
    host.keep_daily_spin = QSpinBox()
    host.keep_daily_spin.setMaximum(365)
    host.keep_daily_spin.setValue(7)
    host.keep_weekly_spin = QSpinBox()
    host.keep_weekly_spin.setMaximum(520)
    host.keep_weekly_spin.setValue(4)
    host.keep_monthly_spin = QSpinBox()
    host.keep_monthly_spin.setMaximum(120)
    host.keep_monthly_spin.setValue(12)
    host.keep_yearly_spin = QSpinBox()
    host.keep_yearly_spin.setMaximum(100)

    keep_wrap = QWidget(config_card)
    keep_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    keep_grid = QGridLayout(keep_wrap)
    keep_grid.setContentsMargins(0, 4, 0, 4)
    keep_grid.setHorizontalSpacing(16)
    keep_grid.setVerticalSpacing(10)
    keep_specs = [
        (0, 0, "Keep Last", host.keep_last_spin, "Most recent snapshots to keep (overrides other rules)"),
        (0, 1, "Keep Hourly", host.keep_hourly_spin, "Number of hourly snapshots to keep"),
        (0, 2, "Keep Daily", host.keep_daily_spin, "Number of daily snapshots to keep"),
        (1, 0, "Keep Weekly", host.keep_weekly_spin, "Number of weekly snapshots to keep"),
        (1, 1, "Keep Monthly", host.keep_monthly_spin, "Number of monthly snapshots to keep"),
        (1, 2, "Keep Yearly", host.keep_yearly_spin, "Number of yearly snapshots to keep"),
    ]
    for r, c, label, spin, tip in keep_specs:
        keep_grid.addWidget(_keep_field(label, spin, tip, parent=keep_wrap), r, c)
        keep_grid.setColumnStretch(c, 1)
    config_card.body.addWidget(keep_wrap)

    policy_hint = QLabel(
        "Use Dry Run in the title bar to preview what would be forgotten, then Apply.",
        config_card,
    )
    policy_hint.setObjectName("pageSubtitle")
    policy_hint.setWordWrap(True)
    config_card.body.addWidget(policy_hint)
    policy_layout.addWidget(config_card, stretch=0)

    output_card = SectionCard("Policy Output", parent=policy_pane)
    output_card.setObjectName("sectionCard")
    output_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    output_card.setVisible(False)
    host._retention_output_card = output_card

    host.retention_output = QPlainTextEdit(output_card)
    host.retention_output.setObjectName("retentionLog")
    host.retention_output.setReadOnly(True)
    host.retention_output.setPlaceholderText("Retention output will appear here…")
    host.retention_output.setMinimumHeight(160)
    host.retention_output.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    output_card.body.addWidget(host.retention_output, stretch=1)
    policy_layout.addWidget(output_card, stretch=1)

    host._retention_output_empty = QLabel(
        "Dry-run or apply a policy to see forget/prune output here.",
        policy_pane,
    )
    host._retention_output_empty.setObjectName("pageSubtitle")
    host._retention_output_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
    host._retention_output_empty.setMinimumHeight(80)
    policy_layout.addWidget(host._retention_output_empty, stretch=1)

    _orig_set_plain = host.retention_output.setPlainText

    def _set_retention_output(text: str, _orig=_orig_set_plain) -> None:
        _orig(text)
        has_text = bool((text or "").strip())
        output_card.setVisible(has_text)
        host._retention_output_empty.setVisible(not has_text)

    host.retention_output.setPlainText = _set_retention_output  # type: ignore[method-assign]
    host.show_retention_output = lambda: (
        output_card.setVisible(True),
        host._retention_output_empty.setVisible(False),
    )

    host.retention_mode_stack.addWidget(policy_pane)

    # ── Schedule mode ───────────────────────────────────────────────
    schedule_pane = QWidget()
    schedule_layout = QVBoxLayout(schedule_pane)
    schedule_layout.setContentsMargins(0, 0, 0, 0)
    schedule_layout.setSpacing(14)

    schedule_card = SectionCard("Schedule Retention", parent=schedule_pane)
    schedule_card.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    schedule_card.body.setContentsMargins(16, 14, 16, 16)
    schedule_card.body.setSpacing(12)

    status_strip = QFrame(schedule_card)
    status_strip.setObjectName("retentionStatusStrip")
    status_strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    status_row = QHBoxLayout(status_strip)
    status_row.setContentsMargins(14, 10, 14, 10)
    status_row.setSpacing(20)

    def _status_col(label: str) -> tuple[QVBoxLayout, QLabel]:
        col = QVBoxLayout()
        col.setSpacing(2)
        lab = QLabel(label, status_strip)
        lab.setObjectName("browseMetaLabel")
        val = QLabel("—", status_strip)
        val.setObjectName("browseMetaValue")
        val.setWordWrap(True)
        col.addWidget(lab)
        col.addWidget(val)
        return col, val

    status_col, host.retention_task_status_label = _status_col("Status")
    status_row.addLayout(status_col, 0)
    schedule_col, host.retention_task_schedule_label = _status_col("Schedule")
    status_row.addLayout(schedule_col, 1)
    task_col, host.retention_task_name_label = _status_col("Task")
    status_row.addLayout(task_col, 1)
    schedule_card.body.addWidget(status_strip)

    host.retention_time_edit = QTimeEdit(schedule_card)
    host.retention_time_edit.setObjectName("retentionTimeEdit")
    host.retention_time_edit.setCursor(Qt.CursorShape.PointingHandCursor)
    host.retention_time_edit.setToolTip("Time of day to run the retention policy")
    host.retention_time_edit.setFixedHeight(34)
    host.retention_time_edit.setFixedWidth(_TIME_W)
    host.retention_time_edit.setTime(QTime(2, 0))
    host.retention_time_edit.setDisplayFormat("HH:mm")
    host.retention_time_edit.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    schedule_card.body.addWidget(
        _form_row("Time", host.retention_time_edit, parent=schedule_card, compact=True)
    )

    host.retention_frequency_combo = QComboBox(schedule_card)
    host.retention_frequency_combo.addItems(["Daily", "Weekly", "Monthly"])
    host.retention_frequency_combo.setCurrentText("Weekly")
    host.retention_frequency_combo.setToolTip(
        "Frequency for running the retention policy automatically"
    )
    host.retention_frequency_combo.setFixedHeight(34)
    host.retention_frequency_combo.setFixedWidth(_FIELD_COMPACT_W)
    host.retention_frequency_combo.setCursor(Qt.CursorShape.PointingHandCursor)
    host.retention_frequency_combo.currentTextChanged.connect(
        host._on_retention_frequency_changed
    )
    schedule_card.body.addWidget(
        _form_row(
            "Frequency",
            host.retention_frequency_combo,
            parent=schedule_card,
            compact=True,
        )
    )

    host.retention_day_combo = QComboBox(schedule_card)
    host.retention_day_combo.setCursor(Qt.CursorShape.PointingHandCursor)
    host.retention_day_combo.setToolTip("Day of the week to run the retention policy")
    host.retention_day_combo.setFixedHeight(34)
    host.retention_day_combo.setFixedWidth(_FIELD_COMPACT_W)
    host.retention_day_combo.addItems(
        ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    )
    host.retention_day_combo.setCurrentText("Sunday")
    host.retention_day_row = _form_row(
        "Day of week", host.retention_day_combo, parent=schedule_card, compact=True
    )
    schedule_card.body.addWidget(host.retention_day_row)

    host.retention_dom_spin = QSpinBox(schedule_card)
    host.retention_dom_spin.setCursor(Qt.CursorShape.PointingHandCursor)
    host.retention_dom_spin.setToolTip(
        "Day of the month to run the retention policy (1–28)"
    )
    host.retention_dom_spin.setFixedHeight(34)
    host.retention_dom_spin.setFixedWidth(_FIELD_COMPACT_W)
    host.retention_dom_spin.setMinimum(1)
    host.retention_dom_spin.setMaximum(28)
    host.retention_dom_spin.setValue(1)
    host.retention_dom_spin.setSuffix(" of month")
    host.retention_dom_row = _form_row(
        "Day of month", host.retention_dom_spin, parent=schedule_card, compact=True
    )
    host.retention_dom_row.setVisible(False)
    schedule_card.body.addWidget(host.retention_dom_row)

    btn_row = QWidget(schedule_card)
    btn_row.setObjectName("retentionTaskBtns")
    btn_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    btn_row.setMinimumHeight(42)
    btn_layout = QHBoxLayout(btn_row)
    btn_layout.setContentsMargins(0, 8, 0, 0)
    btn_layout.setSpacing(8)

    host.retention_create_task_btn = _secondary_btn(
        "Create Scheduled Task",
        host.create_retention_scheduled_task,
        parent=btn_row,
        tooltip="Create or update a system task to run retention automatically",
        min_width=168,
    )
    btn_layout.addWidget(host.retention_create_task_btn, 0)
    btn_layout.addWidget(
        _secondary_btn(
            "View Tasks",
            host.open_task_scheduler,
            parent=btn_row,
            tooltip="Open Task Scheduler to view scheduled tasks",
            min_width=110,
        ),
        0,
    )
    host.retention_delete_task_btn = _secondary_btn(
        "Delete Task",
        host.delete_retention_scheduled_task,
        parent=btn_row,
        tooltip="Delete the scheduled retention task for this repository",
        min_width=110,
    )
    btn_layout.addWidget(host.retention_delete_task_btn, 0)
    btn_layout.addStretch(1)
    schedule_card.body.addWidget(btn_row)

    info = QLabel(
        "Creates a system task that runs retention independently of this application.",
        schedule_card,
    )
    info.setObjectName("retentionInfoLabel")
    info.setWordWrap(True)
    info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    schedule_card.body.addSpacing(8)
    schedule_card.body.addWidget(info)
    schedule_card.body.addStretch(1)

    schedule_layout.addWidget(schedule_card, stretch=1)
    host.retention_mode_stack.addWidget(schedule_pane)

    # Refresh schedule status when repository changes
    host.retention_repo_combo.currentIndexChanged.connect(
        lambda _i: host.refresh_retention_schedule_status()
    )

    def _switch_retention_mode(index: int) -> None:
        host.retention_mode_stack.setCurrentIndex(index)
        if index == 1:
            host.retention_page_subtitle.setText(_SCHEDULE_SUBTITLE)
            host.refresh_retention_schedule_status()
        else:
            host.retention_page_subtitle.setText(_POLICY_SUBTITLE)

    host.retention_mode_group.idClicked.connect(_switch_retention_mode)
    host._switch_retention_mode = _switch_retention_mode

    # Compat: old code looked up QFormLayout labels via this attribute.
    host._retention_schedule_form = None

    return page
