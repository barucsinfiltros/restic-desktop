"""Reusable dashboard card widgets."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor, QEnterEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui.icons import tinted_icon

_ICON_CHIP = 56
_ICON_GLYPH = 30


def _soft_bg(hex_color: str, alpha: float = 0.18) -> str:
    """Return an rgba() stylesheet color from a hex accent."""
    c = QColor(hex_color)
    if not c.isValid():
        c = QColor("#5a8cc8")
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha:.2f})"


class StatCard(QFrame):
    """Metric card: large tinted icon chip + value / label / subtitle."""

    _CARD_HEIGHT = 112
    clicked = Signal()

    def __init__(
        self,
        title: str,
        *,
        icon_name: str = "",
        accent: str = "#5a8cc8",
        subtitle: str = "",
        clickable: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self._CARD_HEIGHT)
        self._clickable = clickable
        self._hover_title = ""
        self._hover_rows: list[tuple[str, str]] = []
        self._hover_footer = ""
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setProperty("clickable", "true")
            self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(16)

        self._chip = QLabel(self)
        self._chip.setObjectName("statCardIcon")
        self._chip.setFixedSize(_ICON_CHIP, _ICON_CHIP)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.addWidget(self._chip, 0, Qt.AlignmentFlag.AlignVCenter)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        # Always parent labels to the card so setVisible() cannot open a tiny
        # top-level window during splash processEvents().
        self.value_label = QLabel("—", self)
        self.value_label.setObjectName("statCardValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        col.addWidget(self.value_label)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("statCardTitle")
        col.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle, self)
        self.subtitle_label.setObjectName("statCardSubtitle")
        # Keep one line so refresh text cannot grow the card / skew the row.
        self.subtitle_label.setWordWrap(False)
        self.subtitle_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.subtitle_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        col.addWidget(self.subtitle_label)
        self.subtitle_label.setVisible(bool(subtitle))

        col.addStretch(1)
        row.addLayout(col, stretch=1)

        self._accent = accent
        self._icon_name = icon_name
        self._apply_icon()

    def set_hover_tip(
        self,
        *,
        title: str,
        rows: Optional[list[tuple[str, str]]] = None,
        footer: str = "",
    ) -> None:
        """Use a themed popup instead of the native OS tooltip."""
        self._hover_title = title or ""
        self._hover_rows = list(rows or [])
        self._hover_footer = footer or ""
        self.setToolTip("")
        self.subtitle_label.setToolTip("")

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            from ui.hover_tip import ThemedHoverTip

            ThemedHoverTip.instance().hide()
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802
        super().enterEvent(event)
        if self._hover_title or self._hover_rows:
            from ui.hover_tip import ThemedHoverTip

            tip = ThemedHoverTip.instance()
            tip.cancel_hide()
            tip.set_content(
                title=self._hover_title,
                rows=self._hover_rows,
                footer=self._hover_footer,
            )
            tip.show_near(QCursor.pos())

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        if self._hover_title or self._hover_rows:
            from ui.hover_tip import ThemedHoverTip

            ThemedHoverTip.instance().schedule_hide(150)

    def _apply_icon(self) -> None:
        self._chip.setStyleSheet(
            f"QLabel#statCardIcon {{"
            f"  background-color: {_soft_bg(self._accent)};"
            f"  border: none;"
            f"  border-radius: 14px;"
            f"}}"
        )
        if self._icon_name:
            self._chip.setPixmap(
                tinted_icon(self._icon_name, self._accent, _ICON_GLYPH).pixmap(
                    _ICON_GLYPH, _ICON_GLYPH
                )
            )

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)

    def set_subtitle(self, text: str, *, tooltip: str = "") -> None:
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))
        # Prefer themed hover tip when configured; otherwise keep native tip.
        if not (self._hover_title or self._hover_rows):
            self.subtitle_label.setToolTip(tooltip or text or "")
        else:
            self.subtitle_label.setToolTip("")
        # Re-assert fixed height so long subtitles cannot stretch the card row.
        self.setFixedHeight(self._CARD_HEIGHT)

    def set_accent(self, color: str) -> None:
        self._accent = color
        self._apply_icon()


class SectionCard(QFrame):
    """Borderless surface card used for charts / tables."""

    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("sectionCardTitle")
        header.addWidget(self.title_label)
        header.addStretch(1)
        self.header_actions = QHBoxLayout()
        self.header_actions.setContentsMargins(0, 0, 0, 0)
        self.header_actions.setSpacing(8)
        header.addLayout(self.header_actions)
        self.body.addLayout(header)
