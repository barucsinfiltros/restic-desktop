"""Modern QPainter chart widgets for the dashboard."""
from __future__ import annotations

import math
from typing import Sequence

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)


def _qcolor(value: str, fallback: str = "#3b82f6") -> QColor:
    c = QColor(value or "")
    return c if c.isValid() else QColor(fallback)


def _lighten(color: QColor, amount: float = 0.28) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        int(color.red() + (255 - color.red()) * amount),
        int(color.green() + (255 - color.green()) * amount),
        int(color.blue() + (255 - color.blue()) * amount),
        color.alpha(),
    )


def _fmt_bytes_short(n: float) -> str:
    """Compact byte label for aggregated chart slices."""
    n = max(0.0, float(n))
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if n < 1024.0 or unit == "PB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


# Muted slate for the aggregated "Other" slice — readable on light and dark cards.
_OTHER_SLICE_COLOR = "#64748b"


def _group_small_slices(
    names: Sequence[str],
    sizes: Sequence[float],
    colors: Sequence[str],
    size_labels: Sequence[str],
    *,
    min_pct: float = 0.04,
    max_named: int = 6,
) -> tuple[list[str], list[float], list[str], list[str], list[str]]:
    """Keep dominant slices; merge tiny ones into a single Other segment.

    Slices under ``min_pct`` of the total (default 4%) are folded into Other.
    At most ``max_named`` named slices remain before Other (so the ring stays
    readable instead of a speckled pie).

    Returns names, sizes, colors, size_labels, and per-row tooltips (full detail
    for Other rows listing folded repository names).
    """
    items = [
        (str(n), max(0.0, float(s)), str(c), str(lbl))
        for n, s, c, lbl in zip(names, sizes, colors, size_labels)
    ]
    total = sum(s for _, s, _, _ in items)

    def _pack(
        rows: list[tuple[str, float, str, str]],
        tips: list[str] | None = None,
    ) -> tuple[list[str], list[float], list[str], list[str], list[str]]:
        names_o = [n for n, _, _, _ in rows]
        sizes_o = [s for _, s, _, _ in rows]
        colors_o = [c for _, _, c, _ in rows]
        labels_o = [lbl for _, _, _, lbl in rows]
        tips_o = tips if tips is not None else [
            f"{n} — {lbl}" if lbl else n for n, lbl in zip(names_o, labels_o)
        ]
        return names_o, sizes_o, colors_o, labels_o, tips_o

    if total <= 0 or len(items) <= 1:
        return _pack(items)

    items.sort(key=lambda x: -x[1])
    main: list[tuple[str, float, str, str]] = []
    other_size = 0.0
    other_names: list[str] = []

    for name, size, color, label in items:
        if size / total < min_pct:
            other_size += size
            other_names.append(name)
        else:
            main.append((name, size, color, label))

    # Cap named slices so the legend/ring stay tidy.
    if len(main) > max_named:
        for name, size, _color, _label in main[max_named:]:
            other_size += size
            other_names.append(name)
        main = main[:max_named]

    if other_size <= 0:
        return _pack(main)

    if not main and len(other_names) <= 2:
        # All slices were tiny and few — keep them visible instead of one Other.
        return _pack(items)

    other_label = _fmt_bytes_short(other_size)
    other_title = f"Other ({len(other_names)})" if len(other_names) > 1 else "Other"
    main.append((other_title, other_size, _OTHER_SLICE_COLOR, other_label))

    tips = [
        f"{n} — {lbl}" if lbl else n for n, _, _, lbl in main[:-1]
    ]
    folded = ", ".join(other_names)
    tips.append(f"{other_title}: {folded} — {other_label}")
    return _pack(main, tips)


class _DonutRing(QWidget):
    """Painted doughnut ring with centre total label."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(168, 168)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._sizes: list[float] = []
        self._colors: list[QColor] = []
        self._total_label = "—"
        self._total_caption = "Total"
        self._bg = QColor("#1a222c")
        self._text = QColor("#e8eef5")
        self._muted = QColor("#8b95a5")
        self._empty_message = "No data available"

    def set_theme(self, *, bg: str, text: str, muted: str, grid: str = "") -> None:
        self._bg = _qcolor(bg, "#1a222c")
        self._text = _qcolor(text, "#e8eef5")
        self._muted = _qcolor(muted, "#8b95a5")
        self.update()

    def set_data(
        self,
        sizes: Sequence[float],
        colors: Sequence[str],
        *,
        total_label: str,
        total_caption: str = "Total",
        empty_message: str = "No data available",
    ) -> None:
        self._sizes = [max(0.0, float(s)) for s in sizes]
        self._colors = [_qcolor(c) for c in colors]
        while len(self._colors) < len(self._sizes):
            self._colors.append(QColor("#3b82f6"))
        self._total_label = total_label or "—"
        self._total_caption = total_caption
        self._empty_message = empty_message
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(self.rect(), self._bg)

        total = sum(self._sizes)
        side = min(self.width(), self.height()) - 8
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        outer = QRectF(cx - side / 2, cy - side / 2, side, side)
        # Thicker ring reads more finished; hole still fits the centre total.
        ring_width = side * 0.26
        inner = QRectF(outer).adjusted(ring_width, ring_width, -ring_width, -ring_width)

        if total <= 0:
            painter.setPen(self._muted)
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_message)
            painter.end()
            return

        start_deg = 90.0  # top
        positive_slices = sum(1 for size in self._sizes if size > 0)
        # A narrow card-coloured gap makes each segment distinct without
        # introducing heavy outlines.
        gap_deg = 1.2 if positive_slices > 1 else 0.0
        for size, color in zip(self._sizes, self._colors):
            if size <= 0:
                continue
            span = (size / total) * 360.0
            draw_span = max(0.2, span - gap_deg)
            draw_start = start_deg - gap_deg / 2.0
            path = QPainterPath()
            path.arcMoveTo(outer, draw_start)
            path.arcTo(outer, draw_start, -draw_span)
            end_deg = draw_start - draw_span
            path.arcTo(inner, end_deg, draw_span)
            path.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillPath(path, color)

            pct = size / total * 100.0
            # Only label substantial wedges so tiny % text doesn't clutter the ring.
            if pct >= 8.0 and span > 18.0:
                mid = start_deg - span / 2.0
                rad = math.radians(mid)
                r = (side / 2.0) - ring_width / 2.0
                lx = cx + math.cos(rad) * r
                ly = cy - math.sin(rad) * r
                painter.setPen(QColor(255, 255, 255, 235))
                font = painter.font()
                font.setPointSize(9)
                font.setBold(True)
                painter.setFont(font)
                label = f"{pct:.0f}%"
                br = painter.fontMetrics().boundingRect(label)
                painter.drawText(
                    int(lx - br.width() / 2),
                    int(ly + br.height() / 3),
                    label,
                )
                painter.setPen(Qt.PenStyle.NoPen)

            start_deg -= span

        # Centre the size/caption as one compact typographic block.
        title_font = QFont(painter.font())
        title_font.setPointSize(17)
        title_font.setBold(True)
        cap_font = QFont(title_font)
        cap_font.setPointSize(10)
        cap_font.setBold(False)

        title_h = QFontMetrics(title_font).height()
        cap_h = QFontMetrics(cap_font).height()
        gap = 2.0
        block_top = cy - (title_h + gap + cap_h) / 2.0

        painter.setPen(self._text)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(inner.left(), block_top, inner.width(), title_h),
            Qt.AlignmentFlag.AlignCenter,
            self._total_label,
        )

        painter.setPen(self._muted)
        painter.setFont(cap_font)
        painter.drawText(
            QRectF(inner.left(), block_top + title_h + gap, inner.width(), cap_h),
            Qt.AlignmentFlag.AlignCenter,
            self._total_caption,
        )
        painter.end()


class _DonutLegend(QWidget):
    """Colour-dot legend: elided name + size, tooltip for full text."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("donutLegend")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(120)
        self.setMaximumWidth(320)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(2, 4, 2, 4)
        self._root.setSpacing(6)
        self._root.addStretch(1)
        self._text = "#e8eef5"
        self._muted = "#8b95a5"
        self._items: list[tuple[str, str, str]] = []

    def set_theme(self, *, text: str, muted: str) -> None:
        self._text = text
        self._muted = muted
        for i in range(self._root.count()):
            item = self._root.itemAt(i)
            w = item.widget() if item else None
            if w is None:
                continue
            name = w.findChild(QLabel, "donutLegendName")
            size = w.findChild(QLabel, "donutLegendSize")
            if name is not None:
                name.setStyleSheet(
                    f"color: {self._text}; background: transparent; border: none; font-size: 11px;"
                )
            if size is not None:
                size.setStyleSheet(
                    f"color: {self._muted}; background: transparent; border: none; font-size: 11px;"
                )

    def set_items(
        self,
        names: Sequence[str],
        sizes: Sequence[str],
        colors: Sequence[str],
        tooltips: Sequence[str] | None = None,
    ) -> None:
        while self._root.count():
            item = self._root.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self._items = list(zip(names, sizes, colors))
        for i, (name, size_text, color) in enumerate(self._items):
            row = QWidget(self)
            row.setObjectName("donutLegendRow")
            tip = (
                tooltips[i]
                if tooltips is not None and i < len(tooltips) and tooltips[i]
                else (f"{name} — {size_text}" if size_text else name)
            )
            row.setToolTip(tip)
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(8)
            hl.setAlignment(Qt.AlignmentFlag.AlignTop)

            dot = QLabel(row)
            dot.setFixedSize(10, 10)
            dot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            dot.setStyleSheet(
                f"background-color: {color}; border: none; border-radius: 5px;"
            )
            hl.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 0, 0, 0)
            text_col.setSpacing(1)

            name_lbl = QLabel(name, row)
            name_lbl.setObjectName("donutLegendName")
            # Ignored width + no wrap: take layout width, clip instead of blowing
            # out of the card into the neighbouring chart.
            name_lbl.setWordWrap(False)
            name_lbl.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            name_lbl.setToolTip(name)
            name_lbl.setStyleSheet(
                f"color: {self._text}; background: transparent; border: none; font-size: 11px;"
            )
            text_col.addWidget(name_lbl)

            size_lbl = QLabel(size_text, row)
            size_lbl.setObjectName("donutLegendSize")
            size_lbl.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            size_lbl.setStyleSheet(
                f"color: {self._muted}; background: transparent; border: none; font-size: 11px;"
            )
            text_col.addWidget(size_lbl)

            hl.addLayout(text_col, stretch=1)
            self._root.addWidget(row)

        self._root.addStretch(1)
        # Elide after layout assigns real widths
        QTimer.singleShot(0, self._elide_names)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._elide_names()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._elide_names()

    def _elide_names(self) -> None:
        """Elide legend names to the legend panel width (not the row's hint width)."""
        avail = max(40, self.width() - 24)
        for i in range(self._root.count()):
            item = self._root.itemAt(i)
            w = item.widget() if item else None
            if w is None:
                continue
            name_lbl = w.findChild(QLabel, "donutLegendName")
            if name_lbl is None:
                continue
            full = name_lbl.toolTip() or name_lbl.text()
            name_lbl.setMaximumWidth(avail)
            fm = QFontMetrics(name_lbl.font())
            name_lbl.setText(fm.elidedText(full, Qt.TextElideMode.ElideRight, avail))


class DonutChart(QFrame):
    """Doughnut + side legend panel."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("donutChart")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)

        # Empty state — full-width centred message (avoids clipping beside the legend)
        self._empty = QLabel('Click "Refresh Dashboard" to load data', self)
        self._empty.setObjectName("donutChartEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setMinimumHeight(240)
        self._stack.addWidget(self._empty)

        data = QWidget(self)
        data.setObjectName("donutChartData")
        row = QHBoxLayout(data)
        row.setContentsMargins(4, 4, 8, 4)
        row.setSpacing(10)

        self._ring = _DonutRing(data)
        row.addWidget(self._ring, stretch=5)

        self._legend = _DonutLegend(data)
        self._legend.setMinimumWidth(140)
        row.addWidget(self._legend, stretch=3)
        self._stack.addWidget(data)

        self._stack.setCurrentIndex(0)
        self._bg = "#1a222c"
        self._muted = "#8b95a5"
        self._apply_empty_style()

    def _apply_empty_style(self) -> None:
        self._empty.setStyleSheet(
            f"QLabel#donutChartEmpty {{"
            f"  color: {self._muted};"
            f"  background: {self._bg};"
            f"  border: none;"
            f"  font-size: 10pt;"
            f"  padding: 24px;"
            f"}}"
        )

    def set_theme(self, *, bg: str, text: str, muted: str, grid: str = "") -> None:
        self._bg = bg
        self._muted = muted
        self.setStyleSheet(f"QFrame#donutChart {{ background: {bg}; border: none; }}")
        self._apply_empty_style()
        self._ring.set_theme(bg=bg, text=text, muted=muted, grid=grid)
        self._legend.set_theme(text=text, muted=muted)

    def set_data(
        self,
        names: Sequence[str],
        sizes: Sequence[float],
        colors: Sequence[str],
        *,
        total_label: str,
        size_labels: Sequence[str] | None = None,
        empty_message: str = "No data available",
    ) -> None:
        has_data = sum(float(s) for s in sizes) > 0
        if not has_data:
            self._empty.setText(empty_message)
            self._stack.setCurrentIndex(0)
            self._ring.set_data([], [], total_label="—", empty_message=empty_message)
            self._legend.set_items([], [], [])
            return

        labels = list(size_labels) if size_labels is not None else [""] * len(names)
        while len(labels) < len(names):
            labels.append("")
        names_g, sizes_g, colors_g, labels_g, tips_g = _group_small_slices(
            names, sizes, colors, labels
        )

        self._stack.setCurrentIndex(1)
        self._ring.set_data(
            sizes_g,
            colors_g,
            total_label=total_label,
            empty_message=empty_message,
        )
        self._legend.set_items(names_g, labels_g, colors_g, tips_g)
        self.update()

    def clear(self, message: str = 'Click "Refresh Dashboard" to load data') -> None:
        self.set_data([], [], [], total_label="—", empty_message=message)


class RoundedBarChart(QWidget):
    """Horizontal repository bars with inline names and hover tooltips."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("roundedBarChart")
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._names: list[str] = []
        self._values: list[float] = []
        self._colors: list[QColor] = []
        self._bar_rects: list[QRectF] = []
        self._bg = QColor("#1a222c")
        self._text = QColor("#e8eef5")
        self._muted = QColor("#8b95a5")
        self._grid = QColor("#2a3544")
        self._empty_message = "No snapshots found"
        self._y_label = "Snapshot Count"
        self._hover_index = -1

    def set_theme(self, *, bg: str, text: str, muted: str, grid: str = "") -> None:
        self._bg = _qcolor(bg, "#1a222c")
        self._text = _qcolor(text, "#e8eef5")
        self._muted = _qcolor(muted, "#8b95a5")
        self._grid = _qcolor(grid or muted, "#2a3544")
        self.update()

    def set_data(
        self,
        names: Sequence[str],
        values: Sequence[float],
        colors: Sequence[str],
        *,
        empty_message: str = "No snapshots found",
        y_label: str = "Snapshot Count",
    ) -> None:
        self._names = list(names)
        self._values = [max(0.0, float(v)) for v in values]
        self._colors = [_qcolor(c) for c in colors]
        while len(self._colors) < len(self._values):
            self._colors.append(QColor("#22c55e"))
        self._empty_message = empty_message
        self._y_label = y_label
        self._hover_index = -1
        self.setToolTip("")
        self.update()

    def clear(self, message: str = "Click Refresh Dashboard to load data") -> None:
        self.set_data([], [], [], empty_message=message)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        hit = -1
        for i, rect in enumerate(self._bar_rects):
            # Treat the full category row as a target, including very short bars.
            hit_rect = QRectF(0, rect.top() - 4, self.width(), rect.height() + 8)
            if hit_rect.contains(pos):
                hit = i
                break
        if hit != self._hover_index:
            self._hover_index = hit
            if 0 <= hit < len(self._names):
                self.setToolTip(f"{self._names[hit]}: {int(self._values[hit])} snapshots")
            else:
                self.setToolTip("")
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover_index >= 0:
            self._hover_index = -1
            self.setToolTip("")
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(self.rect(), self._bg)

        self._bar_rects = []

        if not self._values or sum(self._values) <= 0:
            painter.setPen(self._muted)
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_message)
            painter.end()
            return

        tick_font = QFont(self.font())
        tick_font.setPointSize(8)
        painter.setFont(tick_font)
        fm = painter.fontMetrics()

        # Repository names sit beside their bars, replacing the detached legend.
        longest_name = max((fm.horizontalAdvance(name) for name in self._names), default=0)
        label_w = min(150.0, max(88.0, float(longest_name + 12)))
        left = 12.0 + label_w
        right = 38.0
        top = 12.0
        bottom = 34.0
        plot = QRectF(
            left,
            top,
            max(1.0, self.width() - left - right),
            max(1.0, self.height() - top - bottom),
        )

        max_v = max(self._values) or 1.0
        ticks = 4
        # Equal integer intervals avoid uneven labels such as 0, 2, 4, 7, 9.
        tick_step = max(1, math.ceil(max_v / ticks))
        x_max = float(tick_step * ticks)
        grid_color = QColor(self._grid)
        grid_color.setAlpha(85)
        for i in range(ticks + 1):
            t = i / ticks
            x = plot.left() + t * plot.width()
            painter.setPen(QPen(grid_color, 1, Qt.PenStyle.SolidLine))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            val = i * tick_step
            painter.setPen(self._muted)
            label = str(val)
            br = painter.fontMetrics().boundingRect(label)
            painter.drawText(
                int(x - br.width() / 2),
                int(plot.bottom() + br.height() + 3),
                label,
            )

        n = len(self._values)
        row_h = plot.height() / max(1, n)
        bar_h = max(10.0, min(22.0, row_h * 0.52))
        radius = bar_h / 2.0
        label_rect = QRectF(8, 0, label_w - 4, bar_h + 4)
        track_color = QColor(self._grid)
        track_color.setAlpha(48)

        for i, (name, value, color) in enumerate(
            zip(self._names, self._values, self._colors)
        ):
            cy = plot.top() + row_h * (i + 0.5)
            width = (value / x_max) * plot.width() if x_max else 0.0
            rect = QRectF(plot.left(), cy - bar_h / 2.0, max(width, 0.0), bar_h)
            self._bar_rects.append(rect)

            track = QRectF(plot.left(), rect.top(), plot.width(), bar_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(track_color)
            painter.drawRoundedRect(track, radius, radius)

            painter.setFont(tick_font)
            painter.setPen(self._text if i == self._hover_index else self._muted)
            label_rect.moveTop(cy - label_rect.height() / 2.0)
            elided = fm.elidedText(
                name,
                Qt.TextElideMode.ElideRight,
                int(label_rect.width()),
            )
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                elided,
            )

            path = QPainterPath()
            path.moveTo(rect.left(), rect.top())
            path.lineTo(max(rect.left(), rect.right() - radius), rect.top())
            path.quadTo(rect.right(), rect.top(), rect.right(), rect.center().y())
            path.quadTo(
                rect.right(),
                rect.bottom(),
                max(rect.left(), rect.right() - radius),
                rect.bottom(),
            )
            path.lineTo(rect.left(), rect.bottom())
            path.closeSubpath()

            fill = color
            if i == self._hover_index:
                fill = _lighten(color, 0.10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillPath(path, fill)

            if value > 0:
                painter.setPen(self._text)
                vf = painter.font()
                vf.setPointSize(8)
                vf.setBold(True)
                painter.setFont(vf)
                label = str(int(value))
                br = painter.fontMetrics().boundingRect(label)
                label_x = min(rect.right() + 7, self.width() - br.width() - 4)
                painter.drawText(
                    int(label_x),
                    int(rect.center().y() + br.height() / 3),
                    label,
                )

        axis_font = QFont(self.font())
        axis_font.setPointSize(9)
        painter.setFont(axis_font)
        painter.setPen(self._muted)
        axis_br = painter.fontMetrics().boundingRect(self._y_label)
        painter.drawText(
            int(plot.center().x() - axis_br.width() / 2),
            int(self.height() - 3),
            self._y_label,
        )
        painter.end()
