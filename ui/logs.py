"""Modern logs page builder with find bar."""
from __future__ import annotations

from typing import Any, List, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QKeySequence, QShortcut, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.cards import SectionCard


def _parse_find_query(query: str) -> List[List[str]]:
    """
    Parse find query into OR-groups of AND-terms.

    ``|`` = OR between groups, ``&`` = AND within a group.
    Example: ``error & backup | fail`` → [["error", "backup"], ["fail"]]
    """
    raw = (query or "").strip()
    if not raw:
        return []
    groups: List[List[str]] = []
    for or_part in raw.split("|"):
        terms = [t.strip() for t in or_part.split("&") if t.strip()]
        if terms:
            groups.append(terms)
    return groups


def _line_matches(line: str, groups: List[List[str]]) -> bool:
    """True if line satisfies any OR-group (all AND-terms present, case-insensitive)."""
    if not groups:
        return False
    lower = line.lower()
    for terms in groups:
        if all(term.lower() in lower for term in terms):
            return True
    return False


def _terms_to_highlight(line: str, groups: List[List[str]]) -> List[str]:
    """Terms from matching OR-groups that appear in the line (for highlighting)."""
    if not groups:
        return []
    lower = line.lower()
    found: List[str] = []
    seen = set()
    for terms in groups:
        if all(term.lower() in lower for term in terms):
            for term in terms:
                key = term.lower()
                if key not in seen:
                    seen.add(key)
                    found.append(term)
    return found


class LogFindController:
    """Search / highlight / next-prev for the logs viewer."""

    def __init__(self, host: Any, editor: QPlainTextEdit, find_edit: QLineEdit, count_label: QLabel):
        self.host = host
        self.editor = editor
        self.find_edit = find_edit
        self.count_label = count_label
        self._matches: List[Tuple[int, int]] = []  # (start, length)
        self._index = -1
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self.refresh)

        self.find_edit.textChanged.connect(lambda _t: self._debounce.start())
        self.find_edit.returnPressed.connect(self.find_next)

        # Re-highlight when document changes (new log lines)
        self.editor.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self) -> None:
        if self.find_edit.text().strip():
            self._debounce.start()

    def refresh(self) -> None:
        query = self.find_edit.text()
        groups = _parse_find_query(query)
        self._matches = []
        self._index = -1

        if not groups:
            self.editor.setExtraSelections([])
            self.count_label.setText("")
            return

        doc = self.editor.document()
        block = doc.firstBlock()
        while block.isValid():
            line = block.text()
            if _line_matches(line, groups):
                terms = _terms_to_highlight(line, groups)
                block_pos = block.position()
                lower_line = line.lower()
                for term in terms:
                    start = 0
                    needle = term.lower()
                    while True:
                        idx = lower_line.find(needle, start)
                        if idx < 0:
                            break
                        self._matches.append((block_pos + idx, len(term)))
                        start = idx + max(1, len(term))
            block = block.next()

        self._apply_highlights()
        if self._matches:
            self._index = 0
            self._select_current()
            self.count_label.setText(f"1 / {len(self._matches)}")
        else:
            self.count_label.setText("No matches")

    def _apply_highlights(self) -> None:
        accent = QColor("#5a8cc8")
        try:
            import ui.themes as themes

            theme_id = themes.resolve_theme_id(
                self.host.settings_manager.get("theme")
                if hasattr(self.host, "settings_manager")
                else None
            )
            accent = QColor(themes.get_app_theme(theme_id).accent)
        except Exception:
            pass

        all_fmt = QTextCharFormat()
        all_fmt.setBackground(QColor(accent.red(), accent.green(), accent.blue(), 70))

        current_fmt = QTextCharFormat()
        current_fmt.setBackground(QColor(accent.red(), accent.green(), accent.blue(), 160))
        current_fmt.setForeground(QColor("#ffffff"))

        selections = []
        for i, (start, length) in enumerate(self._matches):
            cur = QTextCursor(self.editor.document())
            cur.setPosition(start)
            cur.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            sel = QPlainTextEdit.ExtraSelection()
            sel.cursor = cur
            sel.format = current_fmt if i == self._index else all_fmt
            selections.append(sel)
        self.editor.setExtraSelections(selections)

    def _select_current(self) -> None:
        if not (0 <= self._index < len(self._matches)):
            return
        start, length = self._matches[self._index]
        cur = QTextCursor(self.editor.document())
        cur.setPosition(start)
        cur.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cur)
        self.editor.centerCursor()
        self._apply_highlights()
        self.count_label.setText(f"{self._index + 1} / {len(self._matches)}")

    def find_next(self) -> None:
        if not self._matches:
            self.refresh()
            return
        if not self._matches:
            return
        self._index = (self._index + 1) % len(self._matches)
        self._select_current()

    def find_prev(self) -> None:
        if not self._matches:
            self.refresh()
            return
        if not self._matches:
            return
        self._index = (self._index - 1) % len(self._matches)
        self._select_current()

    def focus(self) -> None:
        self.find_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.find_edit.selectAll()


def create_logs_page(host: Any) -> QWidget:
    """Build the logs page and attach ``host.log_viewer``."""
    page = QWidget()
    page.setVisible(False)
    page.setObjectName("logsPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(16)

    header = QHBoxLayout()
    header.setSpacing(12)
    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Logs", page)
    title.setObjectName("pageTitle")
    title_col.addWidget(title)
    subtitle = QLabel(
        "Application activity history. Entries are kept according to your log retention setting.",
        page,
    )
    subtitle.setObjectName("pageSubtitle")
    title_col.addWidget(subtitle)
    header.addLayout(title_col, stretch=1)
    layout.addLayout(header)

    log_card = SectionCard("Activity Log", parent=page)
    log_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # Find bar
    find_bar = QWidget(log_card)
    find_bar.setObjectName("logsFindBar")
    find_row = QHBoxLayout(find_bar)
    find_row.setContentsMargins(0, 0, 0, 8)
    find_row.setSpacing(8)

    find_edit = QLineEdit(find_bar)
    find_edit.setObjectName("logsFindEdit")
    find_edit.setPlaceholderText("Find in logs…")
    find_edit.setClearButtonEnabled(True)
    find_edit.setMinimumHeight(30)
    find_edit.setToolTip("Use | for OR and & for AND  (e.g. error|fail   backup&success)")
    find_row.addWidget(find_edit, stretch=1)

    hint = QLabel("| OR   & AND", find_bar)
    hint.setObjectName("logsFindCount")
    hint.setToolTip("Example: error|fail   or   backup&success")
    find_row.addWidget(hint, 0)

    count_label = QLabel("", find_bar)
    count_label.setObjectName("logsFindCount")
    count_label.setMinimumWidth(72)
    find_row.addWidget(count_label, 0)

    prev_btn = QPushButton("Previous", find_bar)
    prev_btn.setObjectName("dialogSecondary")
    prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    prev_btn.setFixedHeight(30)
    find_row.addWidget(prev_btn, 0)

    next_btn = QPushButton("Next", find_bar)
    next_btn.setObjectName("dialogSecondary")
    next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    next_btn.setFixedHeight(30)
    find_row.addWidget(next_btn, 0)

    log_card.body.addWidget(find_bar)

    host.log_viewer = QPlainTextEdit(log_card)
    host.log_viewer.setObjectName("appLog")
    host.log_viewer.setReadOnly(True)
    host.log_viewer.setPlaceholderText("Log output will appear here…")
    host.log_viewer.setMinimumHeight(200)
    log_card.body.addWidget(host.log_viewer, stretch=1)
    layout.addWidget(log_card, stretch=1)

    host._logs_find = LogFindController(host, host.log_viewer, find_edit, count_label)
    prev_btn.clicked.connect(host._logs_find.find_prev)
    next_btn.clicked.connect(host._logs_find.find_next)

    # Ctrl+F only while the Logs page (or a child) has focus — avoids ghosting
    # the find field over other stacked pages via WindowShortcut.
    shortcut = QShortcut(QKeySequence.StandardKey.Find, page)
    shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    shortcut.activated.connect(host._logs_find.focus)

    host.log_find_edit = find_edit
    return page
