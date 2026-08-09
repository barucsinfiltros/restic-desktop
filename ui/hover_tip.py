"""Themed hover tip popup (replaces native QToolTip for richer cards)."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ThemedHoverTip(QFrame):
    """Frameless popup styled like app cards (rounded, bordered, padded)."""

    _instance: Optional["ThemedHoverTip"] = None

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("themedHoverTip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(14, 12, 14, 12)
        self._root.setSpacing(8)

        self._title = QLabel(self)
        self._title.setObjectName("themedHoverTipTitle")
        self._title.setWordWrap(True)
        self._root.addWidget(self._title)

        self._rows_host = QVBoxLayout()
        self._rows_host.setContentsMargins(0, 0, 0, 0)
        self._rows_host.setSpacing(6)
        self._root.addLayout(self._rows_host)

        self._footer = QLabel(self)
        self._footer.setObjectName("themedHoverTipFooter")
        self._footer.setWordWrap(True)
        self._root.addWidget(self._footer)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    @classmethod
    def instance(cls) -> "ThemedHoverTip":
        if cls._instance is None:
            cls._instance = ThemedHoverTip()
        return cls._instance

    def set_content(
        self,
        *,
        title: str,
        rows: list[tuple[str, str]] | None = None,
        footer: str = "",
    ) -> None:
        self._title.setText(title or "")
        self._title.setVisible(bool(title))

        while self._rows_host.count():
            item = self._rows_host.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for name, detail in rows or []:
            row = QWidget(self)
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(10)
            name_lbl = QLabel(name, row)
            name_lbl.setObjectName("themedHoverTipName")
            detail_lbl = QLabel(detail, row)
            detail_lbl.setObjectName("themedHoverTipDetail")
            detail_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lay.addWidget(name_lbl, 1)
            lay.addWidget(detail_lbl, 0)
            self._rows_host.addWidget(row)

        self._footer.setText(footer or "")
        self._footer.setVisible(bool(footer))
        self.adjustSize()

    def show_near(self, global_pos: QPoint, *, delay_ms: int = 0) -> None:
        self._hide_timer.stop()
        # Place below cursor with screen clamping
        x = global_pos.x() + 12
        y = global_pos.y() + 18
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            tip_w = max(self.sizeHint().width(), 260)
            tip_h = max(self.sizeHint().height(), 80)
            if x + tip_w > geo.right() - 8:
                x = geo.right() - tip_w - 8
            if y + tip_h > geo.bottom() - 8:
                y = global_pos.y() - tip_h - 12
            x = max(geo.left() + 8, x)
            y = max(geo.top() + 8, y)
        self.move(x, y)
        if delay_ms > 0:
            QTimer.singleShot(delay_ms, self._safe_show)
        else:
            self._safe_show()

    def _safe_show(self) -> None:
        if not self.isVisible():
            self.show()
        self.raise_()

    def schedule_hide(self, delay_ms: int = 120) -> None:
        self._hide_timer.start(max(0, delay_ms))

    def cancel_hide(self) -> None:
        self._hide_timer.stop()
