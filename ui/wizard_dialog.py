"""Reusable themed stacked-step dialog for guided workflows."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.framed_dialog import FramedDialog


class WizardDialog(FramedDialog):
    """Small wizard shell with step navigation and inline validation."""

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        finish_text: str = "Finish",
        object_name: str = "wizardDialog",
    ):
        super().__init__(
            title,
            parent,
            object_name=object_name,
            show_maximize=False,
            show_minimize=False,
        )
        self.setMinimumSize(680, 560)
        self.resize(720, 620)
        self._steps: list[tuple[str, QWidget, Optional[Callable[[], str]]]] = []
        self._step_labels: list[QLabel] = []
        self._finish_text = finish_text

        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("wizardHeader")
        self._step_row = QHBoxLayout(header)
        self._step_row.setContentsMargins(20, 14, 20, 12)
        self._step_row.setSpacing(8)
        self.body_layout.addWidget(header)

        self.stack = QStackedWidget(self)
        self.stack.setObjectName("wizardStack")
        self.body_layout.addWidget(self.stack, stretch=1)

        footer = QFrame(self)
        footer.setObjectName("backupJobFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 14)
        footer_layout.setSpacing(8)

        self.error_label = QLabel("", footer)
        self.error_label.setObjectName("wizardError")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #ef4444; background: transparent;")
        footer_layout.addWidget(self.error_label, stretch=1)

        self.cancel_btn = QPushButton("Cancel", footer)
        self.cancel_btn.setObjectName("dialogSecondary")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        self.back_btn = QPushButton("Back", footer)
        self.back_btn.setObjectName("dialogSecondary")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.previous_step)
        footer_layout.addWidget(self.back_btn)

        self.next_btn = QPushButton("Next", footer)
        self.next_btn.setObjectName("dialogPrimary")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(self.next_step)
        footer_layout.addWidget(self.next_btn)
        self.body_layout.addWidget(footer)

    def add_step(
        self,
        title: str,
        page: QWidget,
        validator: Optional[Callable[[], str]] = None,
    ) -> None:
        """Append a page; validator returns an error string or an empty string."""
        self._steps.append((title, page, validator))
        self.stack.addWidget(page)
        label = QLabel(self)
        label.setObjectName("wizardStep")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumHeight(28)
        self._step_labels.append(label)
        self._step_row.addWidget(label, stretch=1)
        self._refresh_navigation()

    def current_step(self) -> int:
        return self.stack.currentIndex()

    def show_step(self, index: int) -> None:
        if not self._steps:
            return
        self.stack.setCurrentIndex(max(0, min(index, len(self._steps) - 1)))
        self.error_label.clear()
        self.on_step_changed(self.current_step())
        self._refresh_navigation()

    def previous_step(self) -> None:
        self.show_step(self.current_step() - 1)

    def next_step(self) -> None:
        index = self.current_step()
        if not self._validate(index):
            return
        if index >= len(self._steps) - 1:
            self.finish()
            return
        self.show_step(index + 1)

    def _validate(self, index: int) -> bool:
        if not (0 <= index < len(self._steps)):
            return False
        validator = self._steps[index][2]
        message = validator() if validator is not None else ""
        self.error_label.setText(message or "")
        return not bool(message)

    def _refresh_navigation(self) -> None:
        index = self.current_step()
        count = len(self._steps)
        self.back_btn.setEnabled(index > 0)
        self.next_btn.setText(self._finish_text if count and index == count - 1 else "Next")
        for i, ((title, _, _), label) in enumerate(
            zip(self._steps, self._step_labels)
        ):
            label.setText(f"{i + 1}. {title}")
            label.setProperty("active", "1" if i == index else "0")
            label.setStyleSheet(
                "QLabel { padding: 5px 8px; border-radius: 6px; "
                + (
                    "background: rgba(34, 211, 238, 0.14); color: #22d3ee; "
                    "font-weight: 600;"
                    if i == index
                    else "background: transparent; color: #8b95a5;"
                )
                + " }"
            )

    def on_step_changed(self, index: int) -> None:
        """Hook for subclasses to update review pages or trigger async loading."""

    def finish(self) -> None:
        """Accept by default; subclasses may persist or start work first."""
        self.accept()

