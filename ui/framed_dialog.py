"""Frameless dialog shell matching the main window title-bar chrome."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QRectF
from PyQt6.QtGui import QPainterPath, QRegion
from PyQt6.QtWidgets import QDialog, QFrame, QVBoxLayout, QWidget

from .themes import app_window_icon, polish_combo_popups
from .title_bar import TitleBar


class FramedDialog(QDialog):
    """QDialog with custom title bar + rounded #windowRoot (like the main app)."""

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        object_name: str = "",
        modal: bool = True,
        show_minimize: bool = False,
        show_maximize: bool = True,
        independent: bool = False,
    ):
        # Independent windows (e.g. Notes) must not be parented to the main
        # window — Qt keeps child dialogs stacked above their parent.
        super().__init__(None if independent else parent)
        self.setWindowTitle(title)
        if object_name:
            self.setObjectName(object_name)
        self.setModal(modal)
        self.setWindowIcon(app_window_icon())
        base = Qt.WindowType.Window if independent else Qt.WindowType.Dialog
        self.setWindowFlags(base | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizeGripEnabled(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._root = QFrame()
        self._root.setObjectName("windowRoot")
        self._root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root_layout = QVBoxLayout(self._root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar(
            self,
            title=title,
            show_minimize=show_minimize,
            show_maximize=show_maximize,
        )
        root_layout.addWidget(self.title_bar)

        self._body = QWidget()
        self._body.setObjectName("framedDialogBody")
        self.body_layout = QVBoxLayout(self._body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        root_layout.addWidget(self._body, stretch=1)

        outer.addWidget(self._root)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # Combo popups are separate windows; re-apply palette when dialog appears.
        polish_combo_popups(self)

    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange:
            self.title_bar.sync_max_button()
            self._sync_chrome()
        super().changeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_chrome()

    def _sync_chrome(self) -> None:
        """Square corners when maximized; rounded mask when floating."""
        root = self._root
        maximized = self.isMaximized() or self.isFullScreen()
        root.setProperty("maximized", "1" if maximized else "0")
        root.style().unpolish(root)
        root.style().polish(root)
        if maximized:
            root.clearMask()
        else:
            radius = 10.0
            path = QPainterPath()
            path.addRoundedRect(QRectF(root.rect()), radius, radius)
            root.setMask(QRegion(path.toFillPolygon().toPolygon()))
        root.update()
