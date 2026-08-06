"""Shared helpers for modern data tables."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem


class SortableTableItem(QTableWidgetItem):
    """Table cell that sorts by UserRole when set (e.g. timestamps)."""

    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        if other is None:
            return False
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole)
        if left is not None and right is not None:
            try:
                return left < right
            except TypeError:
                pass
        return super().__lt__(other)


class TableRowHover(QObject):
    """Highlight the full table row on hover (Qt stylesheets are cell-only)."""

    # Persistent base colour for secondary cells (hex string).
    BASE_FG_ROLE = int(Qt.ItemDataRole.UserRole) + 77
    # Items with this role set lighten their own colour on hover/select.
    HOVER_LIGHTEN_ROLE = int(Qt.ItemDataRole.UserRole) + 78
    # Fixed colour that must survive selection (e.g. Success green).
    LOCKED_FG_ROLE = int(Qt.ItemDataRole.UserRole) + 79

    def __init__(
        self,
        table: QTableWidget,
        *,
        nudge_foreground: bool = False,
        paint_background: bool = True,
        lighten_amount: float = 0.08,
    ):
        super().__init__(table)
        self._table = table
        self._row = -1
        self._hover = QBrush(QColor(255, 255, 255, 10))
        self._nudge_foreground = nudge_foreground
        self._paint_background = paint_background
        self._lighten_amount = lighten_amount
        table.viewport().installEventFilter(self)
        table.destroyed.connect(self._on_table_destroyed)
        if nudge_foreground:
            table.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_table_destroyed(self, *_args) -> None:
        self._table = None
        self._row = -1

    def _on_selection_changed(self) -> None:
        # Re-apply after Qt paints selection-color (which would otherwise force bright text).
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, lambda: self._apply(self._row))

    def set_hover_brush(self, brush: QBrush) -> None:
        self._hover = brush

    def set_nudge_foreground(self, enabled: bool) -> None:
        self._nudge_foreground = enabled

    def set_paint_background(self, enabled: bool) -> None:
        self._paint_background = enabled

    @staticmethod
    def _lighten_hex(color: QColor, toward: QColor | None = None, amount: float = 0.08) -> QColor:
        target = toward if toward is not None and toward.isValid() else QColor(255, 255, 255)
        amount = max(0.0, min(1.0, amount))
        r = int(color.red() + (target.red() - color.red()) * amount)
        g = int(color.green() + (target.green() - color.green()) * amount)
        b = int(color.blue() + (target.blue() - color.blue()) * amount)
        return QColor(r, g, b, color.alpha())

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        table = self._table
        if table is None:
            return False
        try:
            viewport = table.viewport()
        except RuntimeError:
            self._table = None
            return False
        if obj is not viewport:
            return False
        et = event.type()
        if et == QEvent.Type.MouseMove:
            index = table.indexAt(event.position().toPoint())
            row = index.row() if index.isValid() else -1
            if row != self._row:
                self._apply(row)
        elif et == QEvent.Type.Leave:
            self._apply(-1)
        return False

    def _base_color(self, item: QTableWidgetItem) -> QColor | None:
        stored = item.data(self.BASE_FG_ROLE)
        if stored:
            c = QColor(str(stored))
            return c if c.isValid() else None
        cur = item.foreground().color()
        return cur if cur.isValid() and cur.alpha() > 0 else None

    def _apply(self, row: int) -> None:
        table = self._table
        if table is None:
            return
        try:
            rows = table.rowCount()
            cols = table.columnCount()
        except RuntimeError:
            self._table = None
            return
        self._row = row
        # Refresh every row so selection + hover stay consistent.
        for r in range(rows):
            for c in range(cols):
                item = table.item(r, c)
                if item is None:
                    continue
                selected = item.isSelected()
                hovering = r == row

                if self._paint_background:
                    if hovering and not selected:
                        item.setBackground(self._hover)
                    elif not selected:
                        item.setBackground(QBrush())

                locked = item.data(self.LOCKED_FG_ROLE)
                if locked:
                    item.setForeground(QColor(str(locked)))
                    continue

                if not self._nudge_foreground or not item.data(self.HOVER_LIGHTEN_ROLE):
                    continue

                base = self._base_color(item)
                if base is None:
                    continue
                if hovering or selected:
                    item.setForeground(
                        self._lighten_hex(base, amount=self._lighten_amount)
                    )
                else:
                    item.setForeground(base)


def make_repo_swatch_cell(
    name: str,
    color: str,
    *,
    parent=None,
):
    """Name cell with a coloured square swatch (repositories table)."""
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

    cell = QWidget(parent)
    cell.setObjectName("repoNameCell")
    row = QHBoxLayout(cell)
    row.setContentsMargins(8, 0, 8, 0)
    row.setSpacing(8)

    swatch = QLabel(cell)
    swatch.setObjectName("repoSwatch")
    swatch.setFixedSize(10, 10)
    swatch.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    swatch.setStyleSheet(
        f"QLabel#repoSwatch {{"
        f"  background-color: {color};"
        f"  border: none;"
        f"  border-radius: 3px;"
        f"}}"
    )
    row.addWidget(swatch, 0, Qt.AlignmentFlag.AlignVCenter)

    label = QLabel(name, cell)
    label.setObjectName("repoNameLabel")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    row.addWidget(label, stretch=1)
    return cell


def make_repo_icon_cell(
    names: list[str],
    color_for,
    *,
    parent=None,
):
    """Jobs-table repository cell: tinted icon chip + plain name (no ellipsis menu)."""
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

    from ui.icons import tinted_icon

    cell = QWidget(parent)
    cell.setObjectName("repoIconCell")
    row = QHBoxLayout(cell)
    # Match jobs table header section padding-left (8px) so icon lines up under "Repository"
    row.setContentsMargins(8, 4, 8, 4)
    row.setSpacing(8)

    if not names:
        empty = QLabel("—", cell)
        empty.setObjectName("repoNameLabel")
        row.addWidget(empty)
        row.addStretch(1)
        return cell

    primary = names[0]
    color = color_for(primary)

    chip = QLabel(cell)
    chip.setObjectName("repoIconChip")
    chip.setFixedSize(28, 28)
    chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
    chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    chip.setStyleSheet(
        f"QLabel#repoIconChip {{"
        f"  background-color: {color};"
        f"  border: none;"
        f"  border-radius: 8px;"
        f"}}"
    )
    chip.setPixmap(tinted_icon("repository.svg", "#ffffff", 15).pixmap(15, 15))
    row.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)

    label_text = primary
    if len(names) > 1:
        label_text = f"{primary} +{len(names) - 1}"
    label = QLabel(label_text, cell)
    label.setObjectName("repoNameLabel")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    if len(names) > 1:
        label.setToolTip(", ".join(names))
    row.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addStretch(1)
    return cell


def make_repo_badges_cell(
    names: list[str],
    color_for,
    *,
    parent=None,
):
    """Back-compat alias for jobs-table repository cells."""
    return make_repo_icon_cell(names, color_for, parent=parent)


def make_snapshot_id_cell(
    short_id: str,
    color: str,
    *,
    parent=None,
):
    """Snapshots-table ID cell: tinted icon chip + short id (repo accent colour)."""
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

    from ui.icons import tinted_icon

    cell = QWidget(parent)
    cell.setObjectName("snapshotIdCell")
    row = QHBoxLayout(cell)
    row.setContentsMargins(8, 4, 8, 4)
    row.setSpacing(8)

    chip = QLabel(cell)
    chip.setObjectName("repoIconChip")
    chip.setFixedSize(28, 28)
    chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
    chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    chip.setStyleSheet(
        f"QLabel#repoIconChip {{"
        f"  background-color: {color};"
        f"  border: none;"
        f"  border-radius: 8px;"
        f"}}"
    )
    chip.setPixmap(tinted_icon("snapshot.svg", "#ffffff", 15).pixmap(15, 15))
    row.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)

    label = QLabel(short_id or "—", cell)
    label.setObjectName("repoNameLabel")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    row.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addStretch(1)
    return cell


def make_snapshot_size_cell(
    size_text: str,
    *,
    ratio: float,
    bar_color: str,
    track_color: str,
    text_color: str,
    tooltip: str = "",
    parent=None,
):
    """Size text + tiny relative bar (ratio vs largest snapshot in the list)."""
    from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

    cell = QWidget(parent)
    cell.setObjectName("snapshotSizeCell")
    row = QHBoxLayout(cell)
    row.setContentsMargins(8, 4, 8, 4)
    row.setSpacing(8)

    label = QLabel(size_text or "—", cell)
    label.setObjectName("snapshotSizeLabel")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    label.setStyleSheet(
        f"QLabel#snapshotSizeLabel {{"
        f"  color: {text_color};"
        f"  background: transparent;"
        f"  border: none;"
        f"  padding: 0;"
        f"  margin: 0;"
        f"}}"
    )
    label.setMinimumWidth(72)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    row.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)

    track = QFrame(cell)
    track.setObjectName("snapshotSizeTrack")
    track.setFixedSize(56, 6)
    track.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    track.setStyleSheet(
        f"QFrame#snapshotSizeTrack {{"
        f"  background-color: {track_color};"
        f"  border: none;"
        f"  border-radius: 3px;"
        f"}}"
    )

    fill_w = max(0, min(56, int(round(56 * max(0.0, min(1.0, ratio))))))
    if fill_w > 0:
        fill = QFrame(track)
        fill.setObjectName("snapshotSizeFill")
        fill.setGeometry(0, 0, fill_w, 6)
        fill.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fill.setStyleSheet(
            f"QFrame#snapshotSizeFill {{"
            f"  background-color: {bar_color};"
            f"  border: none;"
            f"  border-radius: 3px;"
            f"}}"
        )

    row.addWidget(track, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addStretch(1)

    tip = tooltip or (
        "Data added relative to the largest snapshot in this list"
        if size_text and size_text != "—"
        else ""
    )
    if tip:
        cell.setToolTip(tip)
        label.setToolTip(tip)
        track.setToolTip(tip)
    return cell
