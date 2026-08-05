"""Modern icon navigation sidebar."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.icons import icon, tinted_icon

# (label, page_index, icon_file) — page_index -1 = Exit
PRIMARY_NAV = [
    ("Dashboard", 0, "dashboard.svg"),
    ("Repositories", 1, "repository.svg"),
    ("Snapshots", 2, "snapshot.svg"),
    ("Restore Files", 3, "restore.svg"),
    ("Backup Jobs", 4, "jobs.svg"),
    ("Retention Policy", 5, "retention.svg"),
    ("Logs", 6, "logs.svg"),
]

SECONDARY_NAV = [
    ("Settings", 7, "settings.svg"),
    ("Exit", -1, "exit.svg"),
]


class NavSidebar(QFrame):
    """Left navigation rail with SVG icons and grouped Settings/Exit."""

    page_requested = pyqtSignal(int)

    def __init__(
        self,
        *,
        app_name: str = "Restic Manager",
        version: str = "",
        year: str = "",
        muted: str = "#8b95a5",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("navSidebar")
        self.setFixedWidth(240)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._muted = muted
        self.menu_buttons: list[QPushButton] = []
        self._page_to_button: dict[int, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 18, 14, 14)
        root.setSpacing(6)

        brand = QLabel(app_name)
        brand.setObjectName("navBrand")
        root.addWidget(brand)

        if version:
            ver = QLabel(version)
            ver.setObjectName("navVersion")
            root.addWidget(ver)

        root.addSpacing(10)

        for label, page_idx, icon_name in PRIMARY_NAV:
            root.addWidget(self._make_nav_btn(label, page_idx, icon_name))

        root.addSpacing(8)
        divider = QFrame()
        divider.setObjectName("navDivider")
        divider.setFixedHeight(1)
        root.addWidget(divider)
        root.addSpacing(8)

        for label, page_idx, icon_name in SECONDARY_NAV:
            root.addWidget(self._make_nav_btn(label, page_idx, icon_name))

        root.addStretch(1)

        footer = QWidget(self)
        footer.setObjectName("navFooterRow")
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(2, 8, 2, 0)
        footer_row.setSpacing(10)

        brand_icon = QLabel(footer)
        brand_icon.setObjectName("navBrandIcon")
        brand_icon.setFixedSize(36, 36)
        brand_icon.setPixmap(icon("brand.svg", 36).pixmap(36, 36))
        footer_row.addWidget(brand_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        ver_text = version.lstrip("vV") if version else ""
        if ver_text and not ver_text.lower().startswith("version"):
            ver_text = f"Version {ver_text}"
        footer_lines = ver_text
        if year:
            footer_lines = f"{footer_lines}\n© {year}".strip() if footer_lines else f"© {year}"
        footer_label = QLabel(footer_lines, footer)
        footer_label.setObjectName("navFooter")
        footer_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        footer_row.addWidget(footer_label, stretch=1)

        root.addWidget(footer)

        # Default selection
        if 0 in self._page_to_button:
            self.set_active_page(0)

    def _make_nav_btn(self, label: str, page_idx: int, icon_name: str) -> QPushButton:
        btn = QPushButton(f"  {label}")
        btn.setObjectName("navBtn")
        btn.setCheckable(page_idx >= 0)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIcon(tinted_icon(icon_name, self._muted, 18))
        btn.setIconSize(QSize(18, 18))
        btn.setMinimumHeight(40)
        btn.clicked.connect(lambda _checked=False, idx=page_idx: self.page_requested.emit(idx))
        self.menu_buttons.append(btn)
        if page_idx >= 0:
            self._page_to_button[page_idx] = btn
        return btn

    def set_active_page(self, page_index: int) -> None:
        for idx, btn in self._page_to_button.items():
            btn.setChecked(idx == page_index)

    def recolor(self, muted: str, accent: str) -> None:
        """Refresh icon tints after a theme change."""
        self._muted = muted
        all_items = PRIMARY_NAV + SECONDARY_NAV
        for btn, (_label, page_idx, icon_name) in zip(self.menu_buttons, all_items):
            color = accent if page_idx >= 0 and btn.isChecked() else muted
            btn.setIcon(tinted_icon(icon_name, color, 18))
