"""Popup menus with rounded corners (native Fusion chrome ignores QSS radius)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QWidget


class RoundedMenu(QMenu):
    """Frameless translucent menu so stylesheet border-radius is visible."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("roundedMenu")
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
