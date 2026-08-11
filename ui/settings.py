"""Modern settings page builder with in-page section navigation."""
from __future__ import annotations

import sys
from typing import Any, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import ui.themes as themes
from ui.cards import SectionCard
from ui.icons import tinted_icon

_LABEL_W = 200
_FIELD_COMPACT_W = 160
_NAV_W = 200
_NAV_ICON = 18

# (label, subtitle, icon_file)
_SECTIONS = (
    ("Application", "Paths, theme, refresh, and encrypted settings/history backup.", "settings.svg"),
    ("Health", "Backup freshness, integrity checks, and restore tests.", "health.svg"),
    ("Security", "Optional password required when the app starts.", "lock.svg"),
    ("Dependencies", "Check and install required system tools.", "drive.svg"),
    ("About", "Version and application information.", "about.svg"),
)


def _secondary_btn(
    text: str,
    slot,
    *,
    parent: Optional[QWidget] = None,
    tooltip: str = "",
    min_width: int = 0,
    enabled: bool = True,
) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("dialogSecondary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(34)
    btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    btn.setEnabled(enabled)
    if min_width:
        btn.setMinimumWidth(min_width)
    if tooltip:
        btn.setToolTip(tooltip)
    btn.clicked.connect(slot)
    return btn


def _unit_combo(parent: QWidget) -> QComboBox:
    combo = QComboBox(parent)
    combo.setFixedWidth(100)
    combo.setFixedHeight(30)
    combo.setCursor(Qt.CursorShape.PointingHandCursor)
    for unit_id, label in (
        ("hours", "Hours"),
        ("days", "Days"),
        ("months", "Months"),
    ):
        combo.addItem(label, unit_id)
    return combo


def _sync_interval_spin(spin: QSpinBox, unit_combo: QComboBox) -> None:
    unit = unit_combo.currentData() or "hours"
    caps = {"hours": 8760, "days": 365, "months": 24}
    spin.setMaximum(caps.get(unit, 999))
    if spin.value() > spin.maximum():
        spin.setValue(spin.maximum())


def _interval_field(
    host: Any,
    parent: QWidget,
    *,
    spin_attr: str,
    unit_attr: str,
    value: int,
    unit: str,
) -> QWidget:
    spin = QSpinBox(parent)
    spin.setMinimum(1)
    spin.setMaximum(999)
    spin.setFixedWidth(90)
    spin.setFixedHeight(30)
    spin.setValue(max(1, min(999, value)))
    setattr(host, spin_attr, spin)

    unit_combo = _unit_combo(parent)
    idx = unit_combo.findData(unit if unit in ("hours", "days", "months") else "days")
    if idx >= 0:
        unit_combo.setCurrentIndex(idx)
    setattr(host, unit_attr, unit_combo)

    def _on_unit(_text: str = "") -> None:
        _sync_interval_spin(spin, unit_combo)

    unit_combo.currentTextChanged.connect(_on_unit)
    _on_unit()

    field = QWidget(parent)
    row = QHBoxLayout(field)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    row.addWidget(spin, 0)
    row.addWidget(unit_combo, 0)
    row.addStretch(1)
    return field


def _form_row(
    label: str,
    field: QWidget,
    *,
    parent: Optional[QWidget] = None,
    compact: bool = False,
) -> QWidget:
    wrap = QWidget(parent)
    wrap.setObjectName("settingsFormRow")
    wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    row = QHBoxLayout(wrap)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)

    lab = QLabel(label, wrap)
    lab.setObjectName("settingsFormLabel")
    lab.setFixedWidth(_LABEL_W)
    lab.setWordWrap(True)
    lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(lab, 0)

    if compact:
        row.addWidget(field, 0)
        row.addStretch(1)
    else:
        row.addWidget(field, stretch=1)
    return wrap


def set_settings_status(label: QLabel, text: str, kind: str = "muted") -> None:
    """Update a status label with themed objectName (ok / warn / err / muted)."""
    label.setText(text)
    names = {
        "ok": "settingsStatusOk",
        "warn": "settingsStatusWarn",
        "err": "settingsStatusErr",
        "muted": "settingsStatusMuted",
    }
    label.setObjectName(names.get(kind, "settingsStatusMuted"))
    label.style().unpolish(label)
    label.style().polish(label)
    label.update()


def _app_password_active(host: Any) -> tuple[bool, str]:
    """Return (active, storage_suffix) for application password."""
    from restic_manager import load_app_password_credentials

    stored_hash, stored_salt, storage = load_app_password_credentials(
        host.settings_manager
    )
    if stored_hash and stored_salt:
        suffix = f" ({storage})" if storage else ""
        return True, suffix
    return False, ""


def _section_card(parent: QWidget) -> SectionCard:
    """Surface card without a duplicate section title (page header covers that)."""
    card = SectionCard("", parent=parent)
    card.title_label.hide()
    # Drop the empty header row so body content sits flush under the page title.
    header_item = card.body.takeAt(0)
    if header_item is not None:
        header_layout = header_item.layout()
        if header_layout is not None:
            while header_layout.count():
                child = header_layout.takeAt(0)
                w = child.widget()
                if w is not None:
                    w.setParent(None)
    return card


def _wrap_scroll(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setObjectName("settingsScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    holder = QWidget()
    holder.setObjectName("settingsScrollContent")
    hold = QVBoxLayout(holder)
    hold.setContentsMargins(0, 0, 8, 0)
    hold.setSpacing(0)
    hold.addWidget(inner)
    hold.addStretch(1)
    scroll.setWidget(holder)
    return scroll


def _build_application_panel(host: Any, parent: QWidget) -> QWidget:
    card = _section_card(parent)

    host.theme_combo = QComboBox(card)
    themes.populate_theme_combo(host.theme_combo)
    current_theme_id = themes.resolve_theme_id(host.settings_manager.get("theme"))
    current_theme_name = themes.get_app_theme(current_theme_id).name
    idx = host.theme_combo.findText(current_theme_name)
    if idx >= 0:
        host.theme_combo.setCurrentIndex(idx)
    host.theme_combo.setFixedWidth(_FIELD_COMPACT_W)
    host.theme_combo.setFixedHeight(30)
    host.theme_combo.setCursor(Qt.CursorShape.PointingHandCursor)
    host.theme_combo.currentTextChanged.connect(host.change_theme)
    card.body.addWidget(_form_row("Theme", host.theme_combo, parent=card, compact=True))
    card.body.addSpacing(16)

    host.auto_refresh_check = QCheckBox("Enable automatic snapshot refresh", card)
    host.auto_refresh_check.setChecked(
        bool(host.settings_manager.get("auto_refresh_snapshots"))
    )
    card.body.addWidget(
        _form_row("Auto refresh", host.auto_refresh_check, parent=card, compact=True)
    )

    host.refresh_interval_spin = QSpinBox(card)
    host.refresh_interval_spin.setMinimum(10)
    host.refresh_interval_spin.setMaximum(3600)
    try:
        interval = int(host.settings_manager.get("snapshot_refresh_interval") or 60)
    except (TypeError, ValueError):
        interval = 60
    host.refresh_interval_spin.setValue(max(10, min(3600, interval)))
    host.refresh_interval_spin.setSuffix(" seconds")
    host.refresh_interval_spin.setFixedWidth(_FIELD_COMPACT_W)
    host.refresh_interval_spin.setFixedHeight(30)
    card.body.addWidget(
        _form_row("Refresh interval", host.refresh_interval_spin, parent=card, compact=True)
    )
    card.body.addSpacing(16)

    host.repo_status_monitor_check = QCheckBox(
        "Enable automatic repository status checks", card
    )
    host.repo_status_monitor_check.setChecked(
        bool(host.settings_manager.get("auto_check_repository_status"))
    )
    host.repo_status_monitor_check.setToolTip(
        "Periodically test whether configured repositories are reachable while "
        "Restic Desktop is open"
    )
    card.body.addWidget(
        _form_row(
            "Repository status",
            host.repo_status_monitor_check,
            parent=card,
            compact=True,
        )
    )

    host.repo_status_interval_spin = QSpinBox(card)
    host.repo_status_interval_spin.setMinimum(5)
    host.repo_status_interval_spin.setMaximum(1440)
    try:
        status_interval = int(
            host.settings_manager.get("repository_status_check_interval_minutes")
            or 60
        )
    except (TypeError, ValueError):
        status_interval = 60
    host.repo_status_interval_spin.setValue(max(5, min(1440, status_interval)))
    host.repo_status_interval_spin.setSuffix(" minutes")
    host.repo_status_interval_spin.setFixedWidth(_FIELD_COMPACT_W)
    host.repo_status_interval_spin.setFixedHeight(30)
    host.repo_status_interval_spin.setEnabled(
        host.repo_status_monitor_check.isChecked()
    )
    host.repo_status_monitor_check.toggled.connect(
        host.repo_status_interval_spin.setEnabled
    )
    card.body.addWidget(
        _form_row(
            "Status frequency",
            host.repo_status_interval_spin,
            parent=card,
            compact=True,
        )
    )
    card.body.addSpacing(16)

    host.log_retention_spin = QSpinBox(card)
    host.log_retention_spin.setMinimum(1)
    host.log_retention_spin.setMaximum(365)
    try:
        retention_days = int(host.settings_manager.get("log_retention_days") or 30)
    except (TypeError, ValueError):
        retention_days = 30
    host.log_retention_spin.setValue(max(1, min(365, retention_days)))
    host.log_retention_spin.setSuffix(" days")
    host.log_retention_spin.setFixedWidth(_FIELD_COMPACT_W)
    host.log_retention_spin.setFixedHeight(30)
    host.log_retention_spin.setToolTip(
        "How long to keep application activity logs in the history database"
    )
    card.body.addWidget(
        _form_row("Log retention", host.log_retention_spin, parent=card, compact=True)
    )

    host.temp_restore_path_input = QLineEdit(card)
    host.temp_restore_path_input.setText(
        host.settings_manager.get("temp_restore_path") or ""
    )
    host.temp_restore_path_input.setMinimumHeight(30)
    host.temp_restore_path_input.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    temp_field = QWidget(card)
    temp_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    temp_row = QHBoxLayout(temp_field)
    temp_row.setContentsMargins(0, 0, 0, 0)
    temp_row.setSpacing(8)
    temp_row.addWidget(host.temp_restore_path_input, stretch=1)
    temp_row.addWidget(
        _secondary_btn(
            "Browse",
            host.browse_temp_restore_path,
            parent=temp_field,
            min_width=88,
        ),
        0,
    )
    temp_row.addWidget(
        _secondary_btn(
            "Clear",
            host.clear_temp_restore_path,
            parent=temp_field,
            min_width=72,
            tooltip="Delete all files and folders inside the temp restore path",
        ),
        0,
    )
    card.body.addWidget(_form_row("Temp restore path", temp_field, parent=card))

    temp_hint = QLabel(
        "Used for “Restore to original location” (files are staged here, then moved).",
        card,
    )
    temp_hint.setObjectName("settingsHint")
    temp_hint.setWordWrap(True)
    hint_wrap = QWidget(card)
    hint_row = QHBoxLayout(hint_wrap)
    hint_row.setContentsMargins(_LABEL_W + 12, 0, 0, 0)
    hint_row.addWidget(temp_hint, stretch=1)
    card.body.addWidget(hint_wrap)

    app_btns = QWidget(card)
    app_btns.setObjectName("settingsCardBtns")
    app_btns_col = QVBoxLayout(app_btns)
    app_btns_col.setContentsMargins(0, 8, 0, 0)
    app_btns_col.setSpacing(8)

    host.backup_include_history_check = QCheckBox(
        "Include history database (job runs, logs, dashboard cache)",
        app_btns,
    )
    host.backup_include_history_check.setChecked(True)
    host.backup_include_history_check.setCursor(Qt.CursorShape.PointingHandCursor)
    host.backup_include_history_check.setToolTip(
        "Also back up restic_history.db beside your settings file. "
        "Recommended when moving to another PC."
    )
    app_btns_col.addWidget(host.backup_include_history_check)

    app_btns_row = QHBoxLayout()
    app_btns_row.setContentsMargins(0, 0, 0, 0)
    app_btns_row.setSpacing(8)
    app_btns_row.addWidget(
        _secondary_btn(
            "Backup Settings",
            host.backup_settings,
            parent=app_btns,
            tooltip="Export settings (and optional history DB) to an encrypted backup",
            min_width=130,
        ),
        0,
    )
    app_btns_row.addWidget(
        _secondary_btn(
            "Restore Settings",
            host.restore_settings,
            parent=app_btns,
            tooltip="Import settings (and history DB if present) from a backup file",
            min_width=130,
        ),
        0,
    )
    app_btns_row.addStretch(1)
    app_btns_col.addLayout(app_btns_row)
    card.body.addWidget(app_btns)
    return card


def _build_health_panel(host: Any, parent: QWidget) -> QWidget:
    card = _section_card(parent)

    intro = QLabel(
        "These thresholds drive the Dashboard Status card and Repository Health dialog.",
        card,
    )
    intro.setObjectName("settingsHint")
    intro.setWordWrap(True)
    card.body.addWidget(intro)

    from core.health import HealthThresholds

    thresholds = HealthThresholds.from_settings(host.settings_manager)

    card.body.addWidget(
        _form_row(
            "Backup overdue after",
            _interval_field(
                host,
                card,
                spin_attr="health_backup_overdue_spin",
                unit_attr="health_backup_overdue_unit",
                value=thresholds.backup_overdue_value,
                unit=thresholds.backup_overdue_unit,
            ),
            parent=card,
            compact=True,
        )
    )
    host.health_backup_overdue_spin.setToolTip(
        "Mark backups overdue when the last successful job run "
        "(including skip-if-unchanged) is older than this — not merely the newest snapshot"
    )

    card.body.addWidget(
        _form_row(
            "Check every",
            _interval_field(
                host,
                card,
                spin_attr="health_check_interval_spin",
                unit_attr="health_check_interval_unit",
                value=thresholds.check_interval_value,
                unit=thresholds.check_interval_unit,
            ),
            parent=card,
            compact=True,
        )
    )

    card.body.addWidget(
        _form_row(
            "Restore test every",
            _interval_field(
                host,
                card,
                spin_attr="health_restore_interval_spin",
                unit_attr="health_restore_interval_unit",
                value=thresholds.restore_test_interval_value,
                unit=thresholds.restore_test_interval_unit,
            ),
            parent=card,
            compact=True,
        )
    )

    host.health_check_level_combo = QComboBox(card)
    host.health_check_level_combo.setFixedWidth(220)
    host.health_check_level_combo.setFixedHeight(30)
    host.health_check_level_combo.setCursor(Qt.CursorShape.PointingHandCursor)
    for level_id, label in (
        ("quick", "Quick (metadata only)"),
        ("partial", "Partial (10% data)"),
        ("full", "Full data check"),
    ):
        host.health_check_level_combo.addItem(label, level_id)
    current_level = str(
        host.settings_manager.get("health_default_check_level") or "quick"
    ).lower()
    idx = host.health_check_level_combo.findData(current_level)
    if idx >= 0:
        host.health_check_level_combo.setCurrentIndex(idx)
    card.body.addWidget(
        _form_row(
            "Default check level",
            host.health_check_level_combo,
            parent=card,
            compact=True,
        )
    )

    host.health_restore_files_spin = QSpinBox(card)
    host.health_restore_files_spin.setMinimum(1)
    host.health_restore_files_spin.setMaximum(50)
    try:
        max_files = int(host.settings_manager.get("health_restore_test_max_files") or 5)
    except (TypeError, ValueError):
        max_files = 5
    host.health_restore_files_spin.setValue(max(1, min(50, max_files)))
    host.health_restore_files_spin.setSuffix(" files")
    host.health_restore_files_spin.setFixedWidth(_FIELD_COMPACT_W)
    host.health_restore_files_spin.setFixedHeight(30)
    host.health_restore_files_spin.setToolTip(
        "How many sample files to restore during a restore verification test"
    )
    card.body.addWidget(
        _form_row(
            "Restore test sample",
            host.health_restore_files_spin,
            parent=card,
            compact=True,
        )
    )

    note = QLabel(
        "Restore tests extract sample files into your Temp restore path, verify them, "
        "then delete the test folder. They never overwrite original locations.",
        card,
    )
    note.setObjectName("settingsNote")
    note.setWordWrap(True)
    note.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    card.body.addWidget(note)
    return card


def _build_security_panel(host: Any, parent: QWidget) -> QWidget:
    card = _section_card(parent)

    status_strip = QFrame(card)
    status_strip.setObjectName("settingsStatusStrip")
    status_strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    status_strip_row = QHBoxLayout(status_strip)
    status_strip_row.setContentsMargins(14, 10, 14, 10)
    status_strip_row.setSpacing(10)
    status_caption = QLabel("Password protection", status_strip)
    status_caption.setObjectName("settingsFormLabel")
    status_strip_row.addWidget(status_caption, 0)
    host.password_status_label = QLabel(status_strip)
    host.password_status_label.setObjectName("settingsStatusMuted")
    status_strip_row.addWidget(host.password_status_label, stretch=1)
    card.body.addWidget(status_strip)

    password_active, storage_suffix = _app_password_active(host)
    if password_active:
        set_settings_status(
            host.password_status_label,
            f"Active — required at startup{storage_suffix}",
            "ok",
        )
    else:
        set_settings_status(host.password_status_label, "Inactive", "warn")

    if sys.platform == "win32":
        storage_info = (
            "Password hash is stored in the Windows Registry "
            "(HKCU\\Software\\ResticDesktop). "
        )
    else:
        storage_info = (
            "Password hash is stored in the OS keyring "
            "(libsecret / Keychain), not in the settings file. "
        )

    note = QLabel(
        f"{storage_info}"
        "Protection is enforced whenever a password hash is present — clearing "
        "JSON settings cannot bypass it. To disable it, enter your current "
        "password and use Remove Password.",
        card,
    )
    note.setObjectName("settingsNote")
    note.setWordWrap(True)
    note.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    card.body.addWidget(note)

    pw_btns = QWidget(card)
    pw_btns_row = QHBoxLayout(pw_btns)
    pw_btns_row.setContentsMargins(0, 4, 0, 0)
    pw_btns_row.setSpacing(8)
    host.set_password_btn = _secondary_btn(
        "Set Password" if not password_active else "Change Password",
        host.set_app_password,
        parent=pw_btns,
        min_width=140,
    )
    pw_btns_row.addWidget(host.set_password_btn, 0)
    host.remove_password_btn = _secondary_btn(
        "Remove Password",
        host.remove_app_password,
        parent=pw_btns,
        min_width=140,
        enabled=password_active,
    )
    pw_btns_row.addWidget(host.remove_password_btn, 0)
    pw_btns_row.addStretch(1)
    card.body.addWidget(pw_btns)
    return card


def _build_dependencies_panel(host: Any, parent: QWidget) -> QWidget:
    card = _section_card(parent)

    deps_intro = QLabel("Check and install required system dependencies.", card)
    deps_intro.setObjectName("settingsHint")
    deps_intro.setWordWrap(True)
    card.body.addWidget(deps_intro)

    host.restic_path_input = QLineEdit(card)
    host.restic_path_input.setText(host.settings_manager.get("restic_path") or "")
    host.restic_path_input.setMinimumHeight(30)
    host.restic_path_input.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    restic_field = QWidget(card)
    restic_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    restic_row = QHBoxLayout(restic_field)
    restic_row.setContentsMargins(0, 0, 0, 0)
    restic_row.setSpacing(8)
    restic_row.addWidget(host.restic_path_input, stretch=1)
    restic_row.addWidget(
        _secondary_btn(
            "Browse",
            host.browse_restic_path,
            parent=restic_field,
            min_width=88,
        ),
        0,
    )
    restic_row.addWidget(
        _secondary_btn(
            "Test",
            host.test_restic_path,
            parent=restic_field,
            tooltip="Test if restic can be executed from this path",
            min_width=72,
        ),
        0,
    )
    card.body.addWidget(_form_row("Restic path", restic_field, parent=card))
    card.body.addSpacing(12)

    host.rclone_path_input = QLineEdit(card)
    host.rclone_path_input.setText(host.settings_manager.get("rclone_path") or "rclone")
    host.rclone_path_input.setMinimumHeight(30)
    host.rclone_path_input.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    rclone_field = QWidget(card)
    rclone_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    rclone_row = QHBoxLayout(rclone_field)
    rclone_row.setContentsMargins(0, 0, 0, 0)
    rclone_row.setSpacing(8)
    rclone_row.addWidget(host.rclone_path_input, stretch=1)
    rclone_row.addWidget(
        _secondary_btn(
            "Browse",
            host.browse_rclone_path,
            parent=rclone_field,
            min_width=88,
        ),
        0,
    )
    rclone_row.addWidget(
        _secondary_btn(
            "Test",
            host.test_rclone_path,
            parent=rclone_field,
            tooltip="Test if rclone can be executed from this path",
            min_width=72,
        ),
        0,
    )
    card.body.addWidget(_form_row("rclone path", rclone_field, parent=card))
    rclone_hint = QLabel(
        "Required for Cloud repositories (OneDrive, Google Drive, etc.). "
        "Download from https://rclone.org/downloads/",
        card,
    )
    rclone_hint.setObjectName("settingsHint")
    rclone_hint.setWordWrap(True)
    card.body.addWidget(rclone_hint)
    card.body.addSpacing(16)

    deps_row_w = QWidget(card)
    deps_row = QHBoxLayout(deps_row_w)
    deps_row.setContentsMargins(0, 4, 0, 0)
    deps_row.setSpacing(12)
    deps_lab = QLabel("Restic", deps_row_w)
    deps_lab.setObjectName("settingsFormLabel")
    deps_lab.setFixedWidth(_LABEL_W)
    deps_row.addWidget(deps_lab, 0)
    host.restic_status_label = QLabel("Click Check to verify installation", deps_row_w)
    host.restic_status_label.setObjectName("settingsStatusMuted")
    host.restic_status_label.setWordWrap(True)
    deps_row.addWidget(host.restic_status_label, stretch=1)
    host.restic_check_btn = _secondary_btn(
        "Check", host.check_restic_installation, parent=deps_row_w, min_width=88
    )
    deps_row.addWidget(host.restic_check_btn, 0)
    host.restic_install_btn = _secondary_btn(
        "Install", host.install_restic, parent=deps_row_w, min_width=88
    )
    host.restic_install_btn.setVisible(False)
    deps_row.addWidget(host.restic_install_btn, 0)
    card.body.addWidget(deps_row_w)
    return card


def _build_about_panel(host: Any, parent: QWidget) -> QWidget:
    from restic_manager import VERSION, YEAR

    card = _section_card(parent)
    about = QLabel(
        f"Restic Desktop {VERSION}\n"
        f"© {YEAR}\n\n"
        "A free, open-source PySide6 GUI for managing Restic backups.\n"
        "Licensed under the MIT License — use it, share it, improve it.\n\n"
        "Support: buymeacoffee.com/dallustallus",
        card,
    )
    about.setObjectName("settingsAbout")
    about.setAlignment(Qt.AlignmentFlag.AlignCenter)
    about.setWordWrap(True)
    card.body.addWidget(about)
    return card


def refresh_settings_nav_icons(host: Any) -> None:
    """Retint settings section icons for the current theme and selection."""
    nav = getattr(host, "_settings_nav", None)
    if nav is None:
        return
    theme_id = themes.resolve_theme_id(host.settings_manager.get("theme"))
    theme = themes.get_app_theme(theme_id)
    selected = nav.currentRow()
    for i, (_name, _hint, icon_name) in enumerate(_SECTIONS):
        item = nav.item(i)
        if item is None:
            continue
        color = theme.accent if i == selected else theme.muted
        item.setIcon(tinted_icon(icon_name, color, _NAV_ICON))


def create_settings_page(host: Any) -> QWidget:
    """Build the settings page with a left section nav and stacked panels."""
    page = QWidget()
    page.setVisible(False)
    page.setObjectName("settingsPage")
    root = QHBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    # ── Left section rail ────────────────────────────────────────
    rail = QFrame(page)
    rail.setObjectName("settingsNavRail")
    rail.setFixedWidth(_NAV_W)
    rail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    rail_layout = QVBoxLayout(rail)
    rail_layout.setContentsMargins(12, 16, 12, 16)
    rail_layout.setSpacing(8)

    nav_header = QLabel("SETTINGS", rail)
    nav_header.setObjectName("settingsNavHeader")
    rail_layout.addWidget(nav_header)

    nav = QListWidget(rail)
    nav.setObjectName("settingsNav")
    nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    nav.setIconSize(QSize(_NAV_ICON, _NAV_ICON))
    nav.setSpacing(2)
    nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    for name, _hint, _icon in _SECTIONS:
        item = QListWidgetItem(name)
        item.setSizeHint(QSize(0, 34))
        nav.addItem(item)
    rail_layout.addWidget(nav, stretch=1)
    root.addWidget(rail)

    # ── Right content ────────────────────────────────────────────
    content = QWidget(page)
    content.setObjectName("settingsContent")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(24, 18, 24, 20)
    content_layout.setSpacing(12)

    host._settings_section_title = QLabel(_SECTIONS[0][0], content)
    host._settings_section_title.setObjectName("pageTitle")
    content_layout.addWidget(host._settings_section_title)

    host._settings_section_subtitle = QLabel(_SECTIONS[0][1], content)
    host._settings_section_subtitle.setObjectName("pageSubtitle")
    host._settings_section_subtitle.setWordWrap(True)
    content_layout.addWidget(host._settings_section_subtitle)

    stack = QStackedWidget(content)
    stack.setObjectName("settingsStack")
    panels = [
        _build_application_panel(host, content),
        _build_health_panel(host, content),
        _build_security_panel(host, content),
        _build_dependencies_panel(host, content),
        _build_about_panel(host, content),
    ]
    for panel in panels:
        stack.addWidget(_wrap_scroll(panel))
    content_layout.addWidget(stack, stretch=1)
    root.addWidget(content, stretch=1)

    host._settings_nav = nav
    host._settings_stack = stack

    def _on_nav_changed(row: int) -> None:
        if row < 0 or row >= len(_SECTIONS):
            return
        name, hint, _icon = _SECTIONS[row]
        host._settings_section_title.setText(name)
        host._settings_section_subtitle.setText(hint)
        stack.setCurrentIndex(row)
        refresh_settings_nav_icons(host)

    nav.currentRowChanged.connect(_on_nav_changed)
    nav.setCurrentRow(0)
    refresh_settings_nav_icons(host)

    return page
