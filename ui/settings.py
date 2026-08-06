"""Modern settings page builder."""
from __future__ import annotations

import sys
from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import ui.themes as themes
from ui.cards import SectionCard

_LABEL_W = 150
_FIELD_COMPACT_W = 160


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
    # Force stylesheet re-resolve after objectName change
    label.style().unpolish(label)
    label.style().polish(label)
    label.update()


def _app_password_active(host: Any) -> tuple[bool, str]:
    """Return (active, storage_suffix) for application password."""
    if sys.platform == "win32":
        from restic_manager import retrieve_from_registry

        reg_hash = retrieve_from_registry("AppPasswordHash")
        reg_salt = retrieve_from_registry("AppPasswordSalt")
        if reg_hash and reg_salt:
            return True, " (Registry)"
        return False, ""
    if host.settings_manager.get("app_password_hash"):
        return True, " (Settings file)"
    return False, ""


def create_settings_page(host: Any) -> QWidget:
    """Build the settings page and attach widgets onto ``host``."""
    from restic_manager import VERSION, YEAR

    page = QWidget()
    page.setVisible(False)
    page.setObjectName("settingsPage")
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(0)

    scroll = QScrollArea(page)
    scroll.setObjectName("settingsScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    page_layout.addWidget(scroll)

    content = QWidget()
    content.setObjectName("settingsScrollContent")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(16)

    # Header (Save lives on the window title bar)
    header = QHBoxLayout()
    header.setSpacing(12)
    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Settings", content)
    title.setObjectName("pageTitle")
    title_col.addWidget(title)
    subtitle = QLabel(
        "Configure application paths, appearance, security, and licensing.",
        content,
    )
    subtitle.setObjectName("pageSubtitle")
    title_col.addWidget(subtitle)
    header.addLayout(title_col, stretch=1)
    layout.addLayout(header)

    # ── Application ──────────────────────────────────────────────
    app_card = SectionCard("Application", parent=content)

    host.restic_path_input = QLineEdit(app_card)
    host.restic_path_input.setText(host.settings_manager.get("restic_path") or "")
    host.restic_path_input.setMinimumHeight(30)
    host.restic_path_input.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    restic_field = QWidget(app_card)
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
    app_card.body.addWidget(_form_row("Restic path", restic_field, parent=app_card))

    host.theme_combo = QComboBox(app_card)
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
    app_card.body.addWidget(
        _form_row("Theme", host.theme_combo, parent=app_card, compact=True)
    )

    host.auto_refresh_check = QCheckBox("Enable automatic snapshot refresh", app_card)
    host.auto_refresh_check.setChecked(
        bool(host.settings_manager.get("auto_refresh_snapshots"))
    )
    app_card.body.addWidget(
        _form_row("Auto refresh", host.auto_refresh_check, parent=app_card, compact=True)
    )

    host.refresh_interval_spin = QSpinBox(app_card)
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
    app_card.body.addWidget(
        _form_row(
            "Refresh interval",
            host.refresh_interval_spin,
            parent=app_card,
            compact=True,
        )
    )

    host.log_retention_spin = QSpinBox(app_card)
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
    app_card.body.addWidget(
        _form_row(
            "Log retention",
            host.log_retention_spin,
            parent=app_card,
            compact=True,
        )
    )

    host.temp_restore_path_input = QLineEdit(app_card)
    host.temp_restore_path_input.setText(
        host.settings_manager.get("temp_restore_path") or ""
    )
    host.temp_restore_path_input.setMinimumHeight(30)
    host.temp_restore_path_input.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    temp_field = QWidget(app_card)
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
    app_card.body.addWidget(
        _form_row("Temp restore path", temp_field, parent=app_card)
    )

    temp_hint = QLabel(
        "Used for “Restore to original location” (files are staged here, then moved).",
        app_card,
    )
    temp_hint.setObjectName("settingsHint")
    temp_hint.setWordWrap(True)
    # Indent under the field column
    hint_wrap = QWidget(app_card)
    hint_row = QHBoxLayout(hint_wrap)
    hint_row.setContentsMargins(_LABEL_W + 12, 0, 0, 0)
    hint_row.addWidget(temp_hint, stretch=1)
    app_card.body.addWidget(hint_wrap)

    app_btns = QWidget(app_card)
    app_btns.setObjectName("settingsCardBtns")
    app_btns_row = QHBoxLayout(app_btns)
    app_btns_row.setContentsMargins(0, 8, 0, 0)
    app_btns_row.setSpacing(8)
    app_btns_row.addWidget(
        _secondary_btn(
            "Backup Settings",
            host.backup_settings,
            parent=app_btns,
            tooltip="Export settings to a backup file",
            min_width=130,
        ),
        0,
    )
    app_btns_row.addWidget(
        _secondary_btn(
            "Restore Settings",
            host.restore_settings,
            parent=app_btns,
            tooltip="Import settings from a backup file",
            min_width=130,
        ),
        0,
    )
    app_btns_row.addStretch(1)
    app_card.body.addWidget(app_btns)
    layout.addWidget(app_card)

    # ── Security ─────────────────────────────────────────────────
    security_card = SectionCard("Security", parent=content)

    status_strip = QFrame(security_card)
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
    security_card.body.addWidget(status_strip)

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
            "(HKCU\\Software\\ResticManager). "
        )
    else:
        storage_info = "Password hash is stored in the application settings file. "

    note = QLabel(
        f"{storage_info}"
        "Protection uses cryptographic hashing. To disable it, authenticate and use "
        "Remove Password.",
        security_card,
    )
    note.setObjectName("settingsNote")
    note.setWordWrap(True)
    note.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    security_card.body.addWidget(note)

    pw_btns = QWidget(security_card)
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
    security_card.body.addWidget(pw_btns)
    layout.addWidget(security_card)

    # ── Dependencies ─────────────────────────────────────────────
    deps_card = SectionCard("System Dependencies", parent=content)

    deps_intro = QLabel("Check and install required system dependencies.", deps_card)
    deps_intro.setObjectName("settingsHint")
    deps_intro.setWordWrap(True)
    deps_card.body.addWidget(deps_intro)

    deps_row_w = QWidget(deps_card)
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
    deps_card.body.addWidget(deps_row_w)
    layout.addWidget(deps_card)

    # ── License ──────────────────────────────────────────────────
    license_card = SectionCard("License", parent=content)

    host.license_status_label = QLabel(license_card)
    host.license_status_label.setObjectName("settingsStatusMuted")
    host.license_status_label.setWordWrap(True)
    license_card.body.addWidget(host.license_status_label)

    host.machine_id_display = QLineEdit(license_card)
    host.machine_id_display.setReadOnly(True)
    host.machine_id_display.setMinimumHeight(30)
    host.machine_id_display.setObjectName("settingsMachineId")
    host.machine_id_display.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    mid_field = QWidget(license_card)
    mid_row = QHBoxLayout(mid_field)
    mid_row.setContentsMargins(0, 0, 0, 0)
    mid_row.setSpacing(8)
    mid_row.addWidget(host.machine_id_display, stretch=1)
    mid_row.addWidget(
        _secondary_btn("Copy", host.copy_machine_id, parent=mid_field, min_width=72),
        0,
    )
    license_card.body.addWidget(
        _form_row("Machine ID", mid_field, parent=license_card)
    )

    lic_btns = QWidget(license_card)
    lic_btns_row = QHBoxLayout(lic_btns)
    lic_btns_row.setContentsMargins(0, 8, 0, 0)
    lic_btns_row.setSpacing(8)
    lic_btns_row.addWidget(
        _secondary_btn(
            "Update License Key",
            host.update_license_key,
            parent=lic_btns,
            min_width=150,
        ),
        0,
    )
    lic_btns_row.addWidget(
        _secondary_btn(
            "Refresh Status",
            host.refresh_license_status,
            parent=lic_btns,
            min_width=130,
        ),
        0,
    )
    lic_btns_row.addStretch(1)
    license_card.body.addWidget(lic_btns)
    layout.addWidget(license_card)

    # ── About ────────────────────────────────────────────────────
    about_card = SectionCard("About", parent=content)
    about = QLabel(
        f"Restic Backup Manager {VERSION}\n"
        f"© {YEAR}\n\n"
        "A PyQt6 GUI for managing Restic backups",
        about_card,
    )
    about.setObjectName("settingsAbout")
    about.setAlignment(Qt.AlignmentFlag.AlignCenter)
    about.setWordWrap(True)
    about_card.body.addWidget(about)
    layout.addWidget(about_card)

    layout.addStretch(1)
    scroll.setWidget(content)

    # Initialize license display (needs widgets attached)
    host.refresh_license_status()
    return page
