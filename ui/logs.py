"""Modern logs page builder with find bar, level colouring, and filters."""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QKeySequence, QShortcut, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
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


def normalize_log_level(level: Optional[str] = None, message: str = "") -> str:
    """Map stored level + message text to info | warn | error."""
    text = (message or "").lower()
    raw = (level or "info").strip().lower()
    if raw in ("warning", "warn"):
        base = "warn"
    elif raw in ("error", "err", "fatal", "critical"):
        base = "error"
    else:
        base = "info"

    if any(
        token in text
        for token in (" error", "error:", "failed", "failure", "✗", "fatal")
    ) or text.startswith("error"):
        return "error"
    if any(token in text for token in ("warn", "warning", "⚠")):
        return "warn"
    return base


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


def _theme_colors(host: Any) -> dict[str, QColor]:
    muted = QColor("#8b95a5")
    text = QColor("#e8edf4")
    danger = QColor("#f07178")
    warn = QColor("#e6b450")
    try:
        import ui.themes as themes

        theme_id = themes.resolve_theme_id(
            host.settings_manager.get("theme")
            if hasattr(host, "settings_manager")
            else None
        )
        t = themes.get_app_theme(theme_id)
        muted = QColor(t.muted)
        text = QColor(t.text)
        danger = QColor(t.danger)
        warn = QColor("#e6b450")
    except Exception:
        pass
    return {
        "muted": muted,
        "text": text,
        "info": text,
        "warn": warn,
        "error": danger,
    }


def _entry_passes_filter(level: str, filt: str) -> bool:
    if filt == "error":
        return level == "error"
    if filt == "warn":
        return level == "warn"
    return True


def append_formatted_log_line(
    editor: QPlainTextEdit,
    *,
    ts: str,
    level: str,
    message: str,
    host: Any,
) -> None:
    """Append one coloured log line to the viewer."""
    colors = _theme_colors(host)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)

    ts_fmt = QTextCharFormat()
    ts_fmt.setForeground(colors["muted"])
    cursor.insertText(f"[{ts}] ", ts_fmt)

    msg_fmt = QTextCharFormat()
    msg_fmt.setForeground(colors.get(level, colors["text"]))
    cursor.insertText(f"{message}\n", msg_fmt)

    editor.setTextCursor(cursor)
    editor.moveCursor(QTextCursor.MoveOperation.End)


def render_log_entries(host: Any) -> None:
    """Rebuild the log viewer from ``host._log_entries`` and the active filter."""
    viewer = getattr(host, "log_viewer", None)
    if viewer is None:
        return
    entries = getattr(host, "_log_entries", None) or []
    filt = getattr(host, "_logs_filter", "all") or "all"
    empty = getattr(host, "_logs_empty_label", None)

    visible = [
        e
        for e in entries
        if _entry_passes_filter(normalize_log_level(e.get("level"), e.get("message") or ""), filt)
    ]

    viewer.blockSignals(True)
    viewer.clear()
    for entry in visible:
        append_formatted_log_line(
            viewer,
            ts=str(entry.get("ts") or ""),
            level=normalize_log_level(entry.get("level"), entry.get("message") or ""),
            message=str(entry.get("message") or ""),
            host=host,
        )
    viewer.moveCursor(QTextCursor.MoveOperation.End)
    viewer.blockSignals(False)

    if empty is not None:
        if not entries:
            empty.setText("No log entries yet. Activity will appear here as you use the app.")
            empty.setVisible(True)
            viewer.setVisible(False)
        elif not visible:
            empty.setText("No entries match this filter.")
            empty.setVisible(True)
            viewer.setVisible(False)
        else:
            empty.setVisible(False)
            viewer.setVisible(True)

    finder = getattr(host, "_logs_find", None)
    if finder is not None and getattr(finder, "find_edit", None) is not None:
        if finder.find_edit.text().strip():
            finder.refresh()


class LogFindController:
    """Search / highlight / next-prev for the logs viewer."""

    def __init__(
        self, host: Any, editor: QPlainTextEdit, find_edit: QLineEdit, count_label: QLabel
    ):
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
        accent = _theme_colors(self.host).get("info", QColor("#5a8cc8"))
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


def _filter_chip(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("logsFilterBtn")
    btn.setCheckable(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(28)
    return btn


def create_logs_page(host: Any) -> QWidget:
    """Build the logs page and attach ``host.log_viewer``."""
    page = QWidget()
    page.setVisible(False)
    page.setObjectName("logsPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(14)

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
    subtitle.setWordWrap(True)
    title_col.addWidget(subtitle)
    header.addLayout(title_col, stretch=1)
    layout.addLayout(header)

    host._log_entries: list[dict] = []
    host._logs_filter = "all"

    # Toolbar strip: filters + find
    toolbar = QFrame(page)
    toolbar.setObjectName("logsToolbarStrip")
    toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    toolbar_layout = QVBoxLayout(toolbar)
    toolbar_layout.setContentsMargins(12, 10, 12, 10)
    toolbar_layout.setSpacing(10)

    filter_row = QHBoxLayout()
    filter_row.setSpacing(4)
    filter_label = QLabel("Show", toolbar)
    filter_label.setObjectName("logsFindHint")
    filter_row.addWidget(filter_label)

    host.logs_filter_all_btn = _filter_chip("All")
    host.logs_filter_error_btn = _filter_chip("Errors")
    host.logs_filter_warn_btn = _filter_chip("Warnings")
    host.logs_filter_all_btn.setChecked(True)
    host.logs_filter_group = QButtonGroup(page)
    host.logs_filter_group.setExclusive(True)
    host.logs_filter_group.addButton(host.logs_filter_all_btn, 0)
    host.logs_filter_group.addButton(host.logs_filter_error_btn, 1)
    host.logs_filter_group.addButton(host.logs_filter_warn_btn, 2)
    filter_row.addWidget(host.logs_filter_all_btn)
    filter_row.addWidget(host.logs_filter_error_btn)
    filter_row.addWidget(host.logs_filter_warn_btn)
    filter_row.addStretch(1)
    toolbar_layout.addLayout(filter_row)

    find_row = QHBoxLayout()
    find_row.setSpacing(8)
    find_edit = QLineEdit(toolbar)
    find_edit.setObjectName("logsFindEdit")
    find_edit.setPlaceholderText("Find in logs…  (error|fail  or  backup&success)")
    find_edit.setClearButtonEnabled(True)
    find_edit.setMinimumHeight(34)
    find_edit.setToolTip("Use | for OR and & for AND  (e.g. error|fail   backup&success)")
    find_row.addWidget(find_edit, stretch=1)

    count_label = QLabel("", toolbar)
    count_label.setObjectName("logsFindCount")
    count_label.setMinimumWidth(72)
    find_row.addWidget(count_label, 0)

    prev_btn = QPushButton("Previous", toolbar)
    prev_btn.setObjectName("dialogSecondary")
    prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    prev_btn.setFixedHeight(34)
    find_row.addWidget(prev_btn, 0)

    next_btn = QPushButton("Next", toolbar)
    next_btn.setObjectName("dialogSecondary")
    next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    next_btn.setFixedHeight(34)
    find_row.addWidget(next_btn, 0)
    toolbar_layout.addLayout(find_row)
    layout.addWidget(toolbar, 0)

    def _on_filter(index: int) -> None:
        host._logs_filter = {0: "all", 1: "error", 2: "warn"}.get(index, "all")
        render_log_entries(host)

    host.logs_filter_group.idClicked.connect(_on_filter)

    log_card = SectionCard("Activity Log", parent=page)
    log_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    host._logs_empty_label = QLabel(
        "No log entries yet. Activity will appear here as you use the app.",
        log_card,
    )
    host._logs_empty_label.setObjectName("pageSubtitle")
    host._logs_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    host._logs_empty_label.setWordWrap(True)
    host._logs_empty_label.setMinimumHeight(120)
    log_card.body.addWidget(host._logs_empty_label, stretch=1)

    host.log_viewer = QPlainTextEdit(log_card)
    host.log_viewer.setObjectName("appLog")
    host.log_viewer.setReadOnly(True)
    host.log_viewer.setPlaceholderText("Log output will appear here…")
    host.log_viewer.setMinimumHeight(200)
    host.log_viewer.setVisible(False)
    log_card.body.addWidget(host.log_viewer, stretch=1)
    layout.addWidget(log_card, stretch=1)

    host._logs_find = LogFindController(host, host.log_viewer, find_edit, count_label)
    prev_btn.clicked.connect(host._logs_find.find_prev)
    next_btn.clicked.connect(host._logs_find.find_next)

    shortcut = QShortcut(QKeySequence.StandardKey.Find, page)
    shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    shortcut.activated.connect(host._logs_find.focus)

    host.log_find_edit = find_edit
    host.render_log_entries = lambda: render_log_entries(host)
    return page
