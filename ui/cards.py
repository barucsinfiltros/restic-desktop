"""Reusable dashboard card widgets."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui.icons import tinted_icon


class StatCard(QFrame):
    """Metric card: icon chip + large value + muted label."""

    def __init__(
        self,
        title: str,
        *,
        icon_name: str = "",
        accent: str = "#5a8cc8",
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(96)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(14)

        self._chip = QLabel(self)
        self._chip.setObjectName("statCardIcon")
        self._chip.setFixedSize(40, 40)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icon_name:
            self._chip.setPixmap(tinted_icon(icon_name, accent, 20).pixmap(20, 20))
        row.addWidget(self._chip, 0, Qt.AlignmentFlag.AlignTop)

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
        col.addWidget(self.subtitle_label)
        self.subtitle_label.setVisible(bool(subtitle))

        col.addStretch(1)
        row.addLayout(col, stretch=1)

        self._accent = accent
        self._icon_name = icon_name

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    def set_accent(self, color: str) -> None:
        self._accent = color
        if self._icon_name:
            self._chip.setPixmap(
                tinted_icon(self._icon_name, color, 20).pixmap(20, 20)
            )


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
