"""
GUI License Key Generator for Restic Backup Manager

Matches the main app chrome (frameless title bar + Chalk theme).
Admin/developer tool only — keep secure; do not ship to end users.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import sys
from datetime import datetime, timedelta

try:
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QFont, QPainterPath, QRegion
    from PyQt6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QPlainTextEdit,
        QPushButton,
        QRadioButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
        QFileDialog,
    )
except ImportError:
    print("Error: PyQt6 is not installed.")
    print("Please install it with: pip install PyQt6")
    sys.exit(1)

import ui.themes as themes
from ui.cards import SectionCard
from ui.framed_dialog import FramedDialog
from ui.title_bar import TitleBar

# SECRET KEY - Must match the one in restic_manager.py
_SECRET_KEY = b"restic-manager-secret-key-change-this-in-production"
_THEME_ID = "chalk"
_APP_TITLE = "License Key Generator"


def generate_license_key(machine_id: str, expiry_days: int | None = None) -> str:
    """Generate a license key for a specific machine ID."""
    machine_hash = hashlib.sha256(machine_id.encode()).hexdigest()[:16]

    if expiry_days is None:
        expiry_str = "unlimited"
    else:
        expiry_date = datetime.now() + timedelta(days=expiry_days)
        expiry_str = expiry_date.strftime("%Y-%m-%d")

    payload = f"{machine_hash}:{expiry_str}"
    signature = hmac.new(_SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()[:32]

    license_data = f"{machine_hash}:{expiry_str}:{signature}"
    return base64.b64encode(license_data.encode()).decode("utf-8")


def show_framed_message(
    parent,
    title: str,
    message: str,
    *,
    kind: str = "warning",
    min_width: int = 420,
) -> None:
    """Small framed alert matching the main app dialogs."""
    dlg = FramedDialog(
        title,
        parent,
        show_maximize=False,
        show_minimize=False,
        modal=True,
    )
    dlg.setMinimumWidth(min_width)
    dlg.setMaximumWidth(max(min_width + 120, 560))
    dlg.body_layout.setContentsMargins(20, 16, 20, 20)
    dlg.body_layout.setSpacing(14)

    title_lbl = QLabel(title)
    title_lbl.setObjectName("pageTitle")
    title_lbl.setStyleSheet("font-size: 18px;")
    title_lbl.setWordWrap(True)
    dlg.body_layout.addWidget(title_lbl)

    body = QLabel(message)
    body.setObjectName("pageSubtitle")
    body.setWordWrap(True)
    dlg.body_layout.addWidget(body)

    footer = QHBoxLayout()
    footer.addStretch(1)
    ok_btn = QPushButton("OK")
    ok_btn.setObjectName("dialogPrimary" if kind != "error" else "dangerBtn")
    ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    ok_btn.clicked.connect(dlg.accept)
    footer.addWidget(ok_btn)
    dlg.body_layout.addLayout(footer)
    dlg.exec()


class LicenseGeneratorGUI(QMainWindow):
    """Frameless license generator window styled like Restic Manager (Chalk)."""

    def __init__(self):
        super().__init__()
        self.current_license: str | None = None

        self.setWindowTitle(_APP_TITLE)
        self.setWindowIcon(themes.app_window_icon())
        self.setMinimumSize(720, 640)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        root = QFrame()
        root.setObjectName("windowRoot")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root.setMouseTracking(True)
        self._root = root
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar(self, title=_APP_TITLE, show_refresh=False)
        root_layout.addWidget(self.title_bar)

        body = QWidget()
        body.setObjectName("contentArea")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 20)
        body_layout.setSpacing(14)
        root_layout.addWidget(body, stretch=1)
        self.setCentralWidget(root)

        heading = QLabel("License Key Generator")
        heading.setObjectName("pageTitle")
        body_layout.addWidget(heading)

        sub = QLabel(
            "Generate a machine-bound license for Restic Backup Manager. "
            "Paste the customer’s Machine ID from their activation dialog."
        )
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        body_layout.addWidget(sub)

        # --- Machine ID ---
        machine_card = SectionCard("Customer Machine ID", body)
        hint = QLabel("Machine ID from the customer’s License Activation dialog:")
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        machine_card.body.addWidget(hint)

        self.machine_id_input = QLineEdit(machine_card)
        self.machine_id_input.setPlaceholderText("Paste or type Machine ID here…")
        self.machine_id_input.setMinimumHeight(34)
        self.machine_id_input.setFont(QFont("Consolas", 10))
        machine_card.body.addWidget(self.machine_id_input)
        body_layout.addWidget(machine_card)

        # --- License type ---
        type_card = SectionCard("License Type", body)

        self.unlimited_radio = QRadioButton("Unlimited (perpetual license)", type_card)
        self.unlimited_radio.setChecked(True)
        self.unlimited_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.unlimited_radio.toggled.connect(self._update_type_ui)
        type_card.body.addWidget(self.unlimited_radio)

        self.limited_radio = QRadioButton("Time-limited", type_card)
        self.limited_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.limited_radio.toggled.connect(self._update_type_ui)
        type_card.body.addWidget(self.limited_radio)

        days_row = QHBoxLayout()
        days_row.setContentsMargins(28, 0, 0, 0)
        days_row.setSpacing(10)
        days_lab = QLabel("Valid for:")
        days_lab.setObjectName("settingsFormLabel")
        days_row.addWidget(days_lab)
        self.days_spin = QSpinBox(type_card)
        self.days_spin.setMinimumHeight(34)
        self.days_spin.setRange(1, 3650)
        self.days_spin.setValue(365)
        self.days_spin.setSuffix(" days")
        self.days_spin.setEnabled(False)
        self.days_spin.setFixedWidth(140)
        days_row.addWidget(self.days_spin)
        days_row.addStretch(1)
        type_card.body.addLayout(days_row)
        body_layout.addWidget(type_card)

        # --- Generate ---
        gen_row = QHBoxLayout()
        gen_row.addStretch(1)
        self.generate_btn = QPushButton("Generate License Key")
        self.generate_btn.setObjectName("dialogPrimary")
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.setMinimumHeight(36)
        self.generate_btn.setMinimumWidth(200)
        self.generate_btn.clicked.connect(self.generate_license)
        gen_row.addWidget(self.generate_btn)
        body_layout.addLayout(gen_row)

        # --- Output ---
        out_card = SectionCard("Generated License Key", body)
        self.output_text = QPlainTextEdit(out_card)
        self.output_text.setObjectName("restoreLog")
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setPlaceholderText("License key will appear here…")
        self.output_text.setMinimumHeight(180)
        out_card.body.addWidget(self.output_text, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setObjectName("dialogSecondary")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setMinimumHeight(32)
        copy_btn.clicked.connect(self.copy_license)
        actions.addWidget(copy_btn)

        save_btn = QPushButton("Save to File")
        save_btn.setObjectName("dialogSecondary")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setMinimumHeight(32)
        save_btn.clicked.connect(self.save_license)
        actions.addWidget(save_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("dialogSecondary")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setMinimumHeight(32)
        clear_btn.clicked.connect(self.clear_output)
        actions.addWidget(clear_btn)
        actions.addStretch(1)
        out_card.body.addLayout(actions)
        body_layout.addWidget(out_card, stretch=1)

        self.status_label = QLabel("Ready to generate license keys")
        self.status_label.setObjectName("mutedLabel")
        body_layout.addWidget(self.status_label)

    def _update_type_ui(self) -> None:
        self.days_spin.setEnabled(self.limited_radio.isChecked())

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def generate_license(self) -> None:
        machine_id = self.machine_id_input.text().strip()
        if not machine_id:
            show_framed_message(
                self,
                "Missing Machine ID",
                "Please enter a Machine ID before generating a license.",
                kind="warning",
            )
            return

        expiry_days = self.days_spin.value() if self.limited_radio.isChecked() else None

        try:
            license_key = generate_license_key(machine_id, expiry_days)

            lines = [
                "License Key Generated Successfully",
                "=" * 70,
                "",
                f"Machine ID: {machine_id}",
            ]
            if expiry_days is None:
                lines.append("Expiration: Unlimited")
            else:
                expiry_date = datetime.now() + timedelta(days=expiry_days)
                lines.append(
                    f"Expiration: {expiry_date.strftime('%Y-%m-%d')} ({expiry_days} days)"
                )
            lines.extend(
                [
                    "",
                    "-" * 70,
                    "LICENSE KEY:",
                    "-" * 70,
                    license_key,
                    "-" * 70,
                    "",
                    "Send this license key to the customer.",
                    "They can enter it in the License Activation dialog.",
                ]
            )
            self.output_text.setPlainText("\n".join(lines))
            self.current_license = license_key
            self._set_status("License key generated successfully")
        except Exception as exc:
            show_framed_message(
                self,
                "Generation Error",
                f"Error generating license key:\n\n{exc}",
                kind="error",
            )

    def copy_license(self) -> None:
        if not self.current_license:
            show_framed_message(
                self,
                "No License",
                "Please generate a license key first.",
                kind="info",
            )
            return
        QApplication.clipboard().setText(self.current_license)
        self._set_status("License key copied to clipboard")

    def save_license(self) -> None:
        if not self.current_license:
            show_framed_message(
                self,
                "No License",
                "Please generate a license key first.",
                kind="info",
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save License Key",
            "license.key",
            "License Files (*.key);;Text Files (*.txt);;All Files (*.*)",
        )
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.current_license)
            self._set_status(f"License saved to {filename}")
        except Exception as exc:
            show_framed_message(
                self,
                "Save Error",
                f"Error saving license:\n\n{exc}",
                kind="error",
            )

    def clear_output(self) -> None:
        self.output_text.clear()
        self.current_license = None
        self._set_status("Output cleared")

    def changeEvent(self, event) -> None:  # noqa: N802
        from PyQt6.QtCore import QEvent

        if event.type() == QEvent.Type.WindowStateChange:
            self.title_bar.sync_max_button()
            self._sync_chrome()
        super().changeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_chrome()

    def _sync_chrome(self) -> None:
        root = getattr(self, "_root", None)
        if root is None:
            return
        maximized = self.isMaximized() or self.isFullScreen()
        root.setProperty("maximized", "1" if maximized else "0")
        root.style().unpolish(root)
        root.style().polish(root)
        if maximized:
            root.clearMask()
        else:
            path = QPainterPath()
            path.addRoundedRect(QRectF(root.rect()), 10.0, 10.0)
            root.setMask(QRegion(path.toFillPolygon().toPolygon()))
        root.update()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont(themes.prefer_ui_font(), 10))
    app.setApplicationName(_APP_TITLE)
    app.setApplicationVersion("1.0.0")
    app.setWindowIcon(themes.app_window_icon())

    chalk = themes.get_app_theme(_THEME_ID)
    css = themes.build_stylesheet(chalk)
    app.setStyleSheet(css)
    app.setProperty("resticThemeId", _THEME_ID)

    window = LicenseGeneratorGUI()
    window.setStyleSheet(css)
    themes.polish_combo_popups(window, chalk)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
