"""Custom frameless window title bar."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)

from .themes import icon_path

# Pixels of mouse travel before a maximized/fullscreen drag restores the window.
_RESTORE_DRAG_THRESHOLD = 8


class TitleBar(QWidget):
    """Drag to move, double-click to maximize, min / max / close controls."""

    refresh_clicked = pyqtSignal()
    add_repository_clicked = pyqtSignal()
    add_backup_job_clicked = pyqtSignal()
    browse_files_clicked = pyqtSignal()
    start_restore_clicked = pyqtSignal()
    dry_run_retention_clicked = pyqtSignal()
    apply_retention_clicked = pyqtSignal()
    clear_logs_clicked = pyqtSignal()
    save_settings_clicked = pyqtSignal()

    def __init__(
        self,
        window: QWidget,
        title: str = "Restic Manager",
        parent=None,
        *,
        show_minimize: bool = True,
        show_maximize: bool = True,
        show_refresh: bool = False,
    ):
        super().__init__(parent)
        self._window = window
        self._drag_pos: QPoint | None = None
        self._press_global: QPoint | None = None
        self.setObjectName("titleBar")
        self.setFixedHeight(36)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 6, 0)
        row.setSpacing(8)

        icon = QLabel()
        icon.setObjectName("titleBarIcon")
        pix = QIcon(icon_path("app.svg")).pixmap(QSize(18, 18))
        icon.setPixmap(pix)
        icon.setFixedSize(20, 20)
        row.addWidget(icon)

        self._title = QLabel(title)
        self._title.setObjectName("titleBarTitle")
        row.addWidget(self._title)

        self._status = QLabel("")
        self._status.setObjectName("titleBarStatus")
        self._status.hide()
        row.addWidget(self._status)

        row.addStretch(1)

        # Page-context actions (main window only) — same flat style as each other
        self._refresh_btn = self._make_action_btn(
            "  Refresh Dashboard",
            "Refresh Dashboard",
            "refresh.svg",
            self.refresh_clicked.emit,
        )
        self._add_repo_btn = self._make_action_btn(
            "  Add Repository",
            "Add Repository",
            "add.svg",
            self.add_repository_clicked.emit,
        )
        self._add_job_btn = self._make_action_btn(
            "  New Job",
            "New Backup Job",
            "add.svg",
            self.add_backup_job_clicked.emit,
        )
        self._browse_files_btn = self._make_action_btn(
            "  Browse Files",
            "Browse all snapshots in the repository and restore specific files",
            "layers.svg",
            self.browse_files_clicked.emit,
        )
        self._start_restore_btn = self._make_action_btn(
            "  Start Restore",
            "Start Restore",
            "restore.svg",
            self.start_restore_clicked.emit,
        )
        self._dry_run_retention_btn = self._make_action_btn(
            "  Dry Run",
            "Preview retention without deleting snapshots",
            "layers.svg",
            self.dry_run_retention_clicked.emit,
        )
        self._apply_retention_btn = self._make_action_btn(
            "  Apply Policy",
            "Apply retention policy (forget + prune)",
            "retention.svg",
            self.apply_retention_clicked.emit,
        )
        self._clear_logs_btn = self._make_action_btn(
            "  Clear Logs",
            "Clear all stored activity logs",
            "clear.svg",
            self.clear_logs_clicked.emit,
        )
        self._save_settings_btn = self._make_action_btn(
            "  Save Settings",
            "Save application settings",
            "settings.svg",
            self.save_settings_clicked.emit,
        )
        row.addWidget(self._refresh_btn)
        row.addWidget(self._add_repo_btn)
        row.addWidget(self._add_job_btn)
        row.addWidget(self._browse_files_btn)
        row.addWidget(self._start_restore_btn)
        row.addWidget(self._dry_run_retention_btn)
        row.addWidget(self._apply_retention_btn)
        row.addWidget(self._clear_logs_btn)
        row.addWidget(self._save_settings_btn)
        if show_refresh:
            # Default page is Dashboard — show refresh, hide add
            self.set_page_context(0)
        else:
            self._refresh_btn.hide()
            self._add_repo_btn.hide()
            self._add_job_btn.hide()
            self._browse_files_btn.hide()
            self._start_restore_btn.hide()
            self._dry_run_retention_btn.hide()
            self._apply_retention_btn.hide()
            self._clear_logs_btn.hide()
            self._save_settings_btn.hide()

        self._min_btn = QPushButton("–")
        self._min_btn.setObjectName("titleBarBtn")
        self._min_btn.setFixedSize(36, 28)
        self._min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._min_btn.setToolTip("Minimize")
        self._min_btn.clicked.connect(window.showMinimized)

        self._max_btn = QPushButton("□")
        self._max_btn.setObjectName("titleBarBtn")
        self._max_btn.setFixedSize(36, 28)
        self._max_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._max_btn.setToolTip("Maximize")
        self._max_btn.clicked.connect(self._toggle_max)

        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("titleBarCloseBtn")
        self._close_btn.setFixedSize(36, 28)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Close")
        self._close_btn.clicked.connect(window.close)

        for btn in (self._min_btn, self._max_btn, self._close_btn):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        if show_minimize:
            row.addWidget(self._min_btn)
        else:
            self._min_btn.hide()
        if show_maximize:
            row.addWidget(self._max_btn)
        else:
            self._max_btn.hide()
        row.addWidget(self._close_btn)

    def _make_action_btn(self, text: str, tooltip: str, icon_name: str, on_click) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("titleBarActionBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFlat(True)
        btn.setFixedHeight(28)
        try:
            from ui.icons import tinted_icon
            btn.setIcon(tinted_icon(icon_name, "#8b95a5", 16))
            btn.setIconSize(QSize(16, 16))
        except Exception:
            pass
        btn.clicked.connect(on_click)
        return btn

    def set_page_context(self, page_index: int) -> None:
        """Show title-bar actions for the active page; hide elsewhere."""
        # 0 = Dashboard, 1 = Repositories, 2 = Snapshots, 3 = Restore,
        # 4 = Backup Jobs, 5 = Retention Policy, 6 = Logs, 7 = Settings
        show_refresh = page_index in (0, 2)
        self._refresh_btn.setVisible(show_refresh)
        self._add_repo_btn.setVisible(page_index == 1)
        self._add_job_btn.setVisible(page_index == 4)
        self._browse_files_btn.setVisible(page_index == 3)
        self._start_restore_btn.setVisible(page_index == 3)
        self._dry_run_retention_btn.setVisible(page_index == 5)
        self._apply_retention_btn.setVisible(page_index == 5)
        self._clear_logs_btn.setVisible(page_index == 6)
        self._save_settings_btn.setVisible(page_index == 7)
        if page_index == 2:
            self._refresh_btn.setText("  Refresh Snapshots")
            self._refresh_btn.setToolTip("Refresh Snapshots")
        else:
            self._refresh_btn.setText("  Refresh Dashboard")
            self._refresh_btn.setToolTip("Refresh Dashboard")
        if page_index != 0:
            self._status.clear()
            self._status.hide()

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_refreshing(self, busy: bool) -> None:
        """Show busy state on the title-bar refresh control."""
        self._refresh_btn.setEnabled(not busy)
        try:
            from ui.icons import tinted_icon
            color = "#5a8cc8" if busy else "#8b95a5"
            self._refresh_btn.setIcon(tinted_icon("refresh.svg", color, 16))
        except Exception:
            pass
        if busy:
            self._refresh_btn.setText("  Refreshing…")
            tip = self._refresh_btn.toolTip() or ""
            self._status.setText(
                "Updating snapshots" if "Snapshots" in tip else "Updating dashboard"
            )
            self._status.show()
        else:
            tip = self._refresh_btn.toolTip() or ""
            if "Snapshots" in tip:
                self._refresh_btn.setText("  Refresh Snapshots")
            else:
                self._refresh_btn.setText("  Refresh Dashboard")
            self._status.clear()
            self._status.hide()

    def _is_zoomed(self) -> bool:
        return self._window.isMaximized() or self._window.isFullScreen()

    def sync_max_button(self) -> None:
        if self._is_zoomed():
            self._max_btn.setText("❐")
            self._max_btn.setToolTip("Restore")
        else:
            self._max_btn.setText("□")
            self._max_btn.setToolTip("Maximize")

    def _toggle_max(self) -> None:
        if self._window.isFullScreen():
            self._window.showNormal()
        elif self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self.sync_max_button()

    def _restore_for_drag(self, global_pos: QPoint) -> None:
        """Leave maximized/fullscreen and pin the cursor on the title bar."""
        # Relative X on the title bar before restore (0..1).
        local_x = self.mapFromGlobal(global_pos).x()
        bar_w = max(1, self.width())
        ratio = max(0.0, min(1.0, local_x / bar_w))

        if self._window.isFullScreen():
            self._window.showNormal()
        elif self._window.isMaximized():
            self._window.showNormal()

        self.sync_max_button()

        geom = self._window.frameGeometry()
        new_x = global_pos.x() - int(ratio * geom.width())
        new_y = global_pos.y() - max(0, self.mapFromGlobal(global_pos).y())
        self._window.move(new_x, new_y)
        # Continuing drag uses offset from the restored frame top-left.
        self._drag_pos = global_pos - self._window.frameGeometry().topLeft()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            # Use global position delta for reliable dragging on Windows.
            global_pos = event.globalPosition().toPoint()
            self._press_global = global_pos
            self._drag_pos = global_pos - self._window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not (
            self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton
        ):
            super().mouseMoveEvent(event)
            return

        global_pos = event.globalPosition().toPoint()

        if self._is_zoomed():
            # Windows-style: start dragging the title bar → restore, then move.
            if self._press_global is not None:
                delta = global_pos - self._press_global
                if (
                    abs(delta.x()) >= _RESTORE_DRAG_THRESHOLD
                    or abs(delta.y()) >= _RESTORE_DRAG_THRESHOLD
                ):
                    self._restore_for_drag(global_pos)
            event.accept()
            return

        self._window.move(global_pos - self._drag_pos)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_pos = None
        self._press_global = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
