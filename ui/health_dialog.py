"""Repository Health dialog — trust view for backups, integrity, and restore tests."""
from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.health import RepoHealthReport
from ui.framed_dialog import FramedDialog
from ui.icons import tinted_icon
import ui.themes as themes


def _secondary_btn(text: str, slot, *, parent=None, min_width: int = 0) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("dialogSecondary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(32)
    if min_width:
        btn.setMinimumWidth(min_width)
    btn.clicked.connect(slot)
    return btn


def _primary_btn(text: str, slot, *, parent=None, min_width: int = 0) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("dialogPrimary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(34)
    if min_width:
        btn.setMinimumWidth(min_width)
    btn.clicked.connect(slot)
    return btn


def _kv_row(label: str, value: str, *, value_object: str = "healthKvValue") -> QWidget:
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 2, 0, 2)
    lay.setSpacing(8)
    lab = QLabel(label)
    lab.setObjectName("healthKvLabel")
    val = QLabel(value)
    val.setObjectName(value_object)
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    val.setWordWrap(True)
    lay.addWidget(lab, 0)
    lay.addWidget(val, 1)
    return row


class RepositoryHealthDialog(FramedDialog):
    """Detailed health dialog for a single repository (switchable via combo)."""

    def __init__(
        self,
        host: Any,
        *,
        initial_repo: str = "",
        parent=None,
    ):
        super().__init__(
            "Repository Health",
            parent or host,
            show_maximize=True,
            show_minimize=False,
            modal=True,
        )
        self._host = host
        self.setMinimumSize(960, 820)
        self.resize(1020, 880)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("healthScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_layout.addWidget(scroll, stretch=1)

        content = QWidget()
        content.setObjectName("healthContent")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 16, 24, 12)
        self._content_layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Repository Health")
        title.setObjectName("pageTitle")
        title_col.addWidget(title)
        sub = QLabel("Detailed health and integrity information for this repository.")
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        title_col.addWidget(sub)
        header.addLayout(title_col, stretch=1)

        self.repo_combo = QComboBox()
        self.repo_combo.setObjectName("healthRepoCombo")
        self.repo_combo.setMinimumHeight(34)
        self.repo_combo.setMinimumWidth(180)
        self.repo_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        repos = host.settings_manager.get("repositories") or []
        for repo in repos:
            name = repo.get("name") or ""
            if name:
                self.repo_combo.addItem(name)
        if initial_repo:
            idx = self.repo_combo.findText(initial_repo)
            if idx >= 0:
                self.repo_combo.setCurrentIndex(idx)
        self.repo_combo.currentTextChanged.connect(self._on_repo_changed)
        header.addWidget(self.repo_combo, 0, Qt.AlignmentFlag.AlignTop)
        self._content_layout.addLayout(header)

        # Dynamic body host
        self._body_host = QVBoxLayout()
        self._body_host.setSpacing(14)
        self._content_layout.addLayout(self._body_host)
        self._content_layout.addStretch(1)
        scroll.setWidget(content)

        # Fixed footer outside scroll so Close never clips
        footer_bar = QFrame()
        footer_bar.setObjectName("healthFooter")
        footer_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer = QHBoxLayout(footer_bar)
        footer.setContentsMargins(24, 12, 24, 16)
        footer.setSpacing(8)
        footer.addStretch(1)
        footer.addWidget(_primary_btn("Close", self.accept, min_width=100))
        self.body_layout.addWidget(footer_bar, stretch=0)

        self._report: Optional[RepoHealthReport] = None
        self.refresh()

    def current_repo_name(self) -> str:
        return self.repo_combo.currentText().strip()

    def _on_repo_changed(self, _name: str) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Rebuild body from host-computed report."""
        while self._body_host.count():
            item = self._body_host.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        name = self.current_repo_name()
        if not name:
            empty = QLabel("Add a repository to view health details.")
            empty.setObjectName("pageSubtitle")
            self._body_host.addWidget(empty)
            return

        report = self._host.build_repo_health_report(name)
        self._report = report
        self._body_host.addWidget(self._build_hero(report))
        self._body_host.addWidget(self._build_detail_row(report))
        self._body_host.addWidget(self._build_bottom_row(report))

    def _theme(self):
        theme_id = themes.resolve_theme_id(self._host.settings_manager.get("theme"))
        return themes.get_app_theme(theme_id)

    def _status_color(self, status: str) -> str:
        t = self._theme()
        return {
            "healthy": getattr(t, "ok", "#22c55e"),
            "warning": "#d97706",
            "critical": getattr(t, "danger", "#ef4444"),
            "unknown": getattr(t, "muted", "#8b95a5"),
        }.get(status, t.muted)

    def _build_hero(self, report: RepoHealthReport) -> QFrame:
        card = QFrame()
        card.setObjectName("healthHero")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(card)
        row.setContentsMargins(18, 16, 18, 16)
        row.setSpacing(20)

        left = QHBoxLayout()
        left.setSpacing(14)
        icon = QLabel()
        icon.setFixedSize(56, 56)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color = self._status_color(report.status)
        icon.setPixmap(tinted_icon("health.svg", color, 36).pixmap(36, 36))
        left.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        status = QLabel(report.status_label)
        status.setObjectName("healthHeroStatus")
        status.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 700;")
        text_col.addWidget(status)
        msg = QLabel(report.status_message)
        msg.setObjectName("healthHeroMsg")
        msg.setWordWrap(True)
        text_col.addWidget(msg)
        left.addLayout(text_col, stretch=1)
        row.addLayout(left, stretch=1)

        metrics = QHBoxLayout()
        metrics.setSpacing(18)
        for icon_name, label, value, badge, badge_ok in (
            (
                "snapshot.svg",
                "Last Backup",
                report.last_backup_label,
                report.last_backup_status,
                report.last_backup_status == "Successful",
            ),
            (
                "health.svg",
                "Last Check",
                report.last_check_label,
                report.last_check_result,
                report.last_check_result == "Passed",
            ),
            (
                "restore.svg",
                "Last Restore Test",
                report.last_restore_test_label,
                report.last_restore_test_result,
                report.last_restore_test_result == "Passed",
            ),
            (
                "health.svg",
                "Health Score",
                f"{report.score} / 100",
                report.score_label,
                report.score >= 75,
            ),
        ):
            metrics.addWidget(
                self._metric_cell(icon_name, label, value, badge, badge_ok)
            )
        row.addLayout(metrics, stretch=0)
        return card

    def _metric_cell(
        self,
        icon_name: str,
        label: str,
        value: str,
        badge: str,
        ok: bool,
    ) -> QWidget:
        t = self._theme()
        wrap = QWidget()
        wrap.setMinimumWidth(120)
        col = QVBoxLayout(wrap)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(6)
        ic = QLabel()
        ic.setPixmap(tinted_icon(icon_name, t.muted, 14).pixmap(14, 14))
        top.addWidget(ic)
        lab = QLabel(label)
        lab.setObjectName("healthMetricLabel")
        top.addWidget(lab)
        top.addStretch(1)
        col.addLayout(top)
        val = QLabel(value)
        val.setObjectName("healthMetricValue")
        col.addWidget(val)
        badge_lbl = QLabel(badge)
        badge_lbl.setObjectName("healthMetricOk" if ok else "healthMetricWarn")
        col.addWidget(badge_lbl)
        return wrap

    def _build_detail_row(self, report: RepoHealthReport) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # Backup Status
        backup = self._detail_card(
            "Backup Status",
            "jobs.svg",
            "#3b82f6",
            [
                ("Last Backup", report.last_backup_label),
                ("Last Successful Backup", report.last_backup_label),
                ("Next Scheduled Backup", report.next_scheduled_label),
                ("Backup Jobs", str(report.job_count)),
                ("Failed Jobs", str(report.failed_jobs)),
                ("Overdue Jobs", str(report.overdue_jobs)),
            ],
            "View Backup Jobs",
            lambda: self._action("view_jobs"),
        )
        lay.addWidget(backup, stretch=1)

        # Integrity
        size_txt = self._host.format_bytes(report.total_size) if report.total_size else "—"
        result_obj = (
            "healthKvOk"
            if report.last_check_result == "Passed"
            else (
                "healthKvErr"
                if report.last_check_result == "Failed"
                else "healthKvValue"
            )
        )
        integrity = self._detail_card(
            "Repository Integrity",
            "health.svg",
            "#06b6d4",
            [
                ("Last Check", report.last_check_label),
                ("Check Result", report.last_check_result, result_obj),
                ("Next Recommended", report.next_check_label),
                ("Total Snapshots", str(report.snapshot_count)),
                ("Total Size", size_txt),
            ],
            "Run Check Now",
            lambda: self._action("run_check"),
        )
        lay.addWidget(integrity, stretch=1)

        # Restore
        verified = (
            self._host.format_bytes(report.restore_bytes)
            if report.restore_bytes
            else "—"
        )
        restore_obj = (
            "healthKvOk"
            if report.last_restore_test_result == "Passed"
            else (
                "healthKvErr"
                if report.last_restore_test_result == "Failed"
                else "healthKvValue"
            )
        )
        restore = self._detail_card(
            "Restore Assurance",
            "restore.svg",
            "#a855f7",
            [
                ("Last Restore Test", report.last_restore_test_label),
                ("Test Result", report.last_restore_test_result, restore_obj),
                ("Files Tested", str(report.restore_files) if report.restore_files else "—"),
                ("Data Verified", verified),
                ("Next Recommended", report.next_restore_label),
            ],
            "Run Restore Test",
            lambda: self._action("run_restore_test"),
        )
        lay.addWidget(restore, stretch=1)
        return row

    def _detail_card(
        self,
        title: str,
        icon_name: str,
        accent: str,
        rows: list,
        button_text: str,
        on_click: Callable[[], None],
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("healthDetailCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(tinted_icon(icon_name, accent, 18).pixmap(18, 18))
        head.addWidget(ic)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("healthDetailTitle")
        head.addWidget(title_lbl)
        head.addStretch(1)
        lay.addLayout(head)

        for row in rows:
            if len(row) == 3:
                lay.addWidget(_kv_row(row[0], row[1], value_object=row[2]))
            else:
                lay.addWidget(_kv_row(row[0], row[1]))

        lay.addStretch(1)
        lay.addWidget(_secondary_btn(button_text, on_click, min_width=120), 0)
        return card

    def _build_bottom_row(self, report: RepoHealthReport) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(self._events_card(report), stretch=1)
        lay.addWidget(self._recommendations_card(report), stretch=1)
        return row

    def _events_card(self, report: RepoHealthReport) -> QFrame:
        card = QFrame()
        card.setObjectName("healthDetailCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        title = QLabel("Recent Events")
        title.setObjectName("healthDetailTitle")
        lay.addWidget(title)

        if not report.events:
            empty = QLabel("No recent job activity for this repository.")
            empty.setObjectName("healthKvLabel")
            empty.setWordWrap(True)
            lay.addWidget(empty)
        else:
            for ev in report.events[:6]:
                lay.addWidget(self._event_row(ev))

        lay.addStretch(1)
        link = QPushButton("View All Logs  →")
        link.setObjectName("linkBtn")
        link.setFlat(True)
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(lambda: self._action("view_logs"))
        lay.addWidget(link, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _event_row(self, ev) -> QWidget:
        t = self._theme()
        color = {
            "ok": getattr(t, "ok", "#22c55e"),
            "warn": "#d97706",
            "err": getattr(t, "danger", "#ef4444"),
        }.get(ev.kind, t.muted)
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(10)
        ic = QLabel()
        icon_name = "health.svg" if ev.kind == "ok" else "about.svg"
        ic.setPixmap(tinted_icon(icon_name, color, 16).pixmap(16, 16))
        row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        title = QLabel(ev.title)
        title.setObjectName("healthEventTitle")
        col.addWidget(title)
        detail = QLabel(ev.detail)
        detail.setObjectName("healthKvLabel")
        detail.setWordWrap(True)
        col.addWidget(detail)
        row.addLayout(col, stretch=1)
        when = QLabel(ev.when)
        when.setObjectName("healthKvLabel")
        row.addWidget(when, 0, Qt.AlignmentFlag.AlignTop)
        return wrap

    def _recommendations_card(self, report: RepoHealthReport) -> QFrame:
        card = QFrame()
        card.setObjectName("healthDetailCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        title = QLabel("Recommendations")
        title.setObjectName("healthDetailTitle")
        lay.addWidget(title)

        for rec in report.recommendations:
            lay.addWidget(self._rec_row(rec))
        lay.addStretch(1)
        return card

    def _rec_row(self, rec) -> QWidget:
        t = self._theme()
        color_map = {
            "check": "#d97706",
            "restore": "#a855f7",
            "jobs": getattr(t, "danger", "#ef4444"),
            "praise": getattr(t, "ok", "#22c55e"),
            "warning": "#d97706",
        }
        icon_map = {
            "check": "health.svg",
            "restore": "restore.svg",
            "jobs": "jobs.svg",
            "praise": "health.svg",
            "warning": "about.svg",
        }
        wrap = QFrame()
        wrap.setObjectName("healthRecRow")
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(wrap)
        row.setContentsMargins(10, 10, 10, 10)
        row.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(
            tinted_icon(
                icon_map.get(rec.kind, "about.svg"),
                color_map.get(rec.kind, t.muted),
                18,
            ).pixmap(18, 18)
        )
        row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel(rec.title)
        title.setObjectName("healthEventTitle")
        col.addWidget(title)
        detail = QLabel(rec.detail)
        detail.setObjectName("healthKvLabel")
        detail.setWordWrap(True)
        col.addWidget(detail)
        row.addLayout(col, stretch=1)
        if rec.action and rec.action_id:
            btn = _secondary_btn(
                rec.action,
                lambda _=False, aid=rec.action_id: self._action(aid),
                min_width=100,
            )
            row.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
        return wrap

    def _action(self, action_id: str) -> None:
        name = self.current_repo_name()
        if action_id == "run_check":
            self._host.run_repository_integrity_check(
                name, on_complete=lambda *_a: self.refresh()
            )
        elif action_id == "run_restore_test":
            self._host.run_repository_restore_test(
                name, on_complete=lambda *_a: self.refresh()
            )
        elif action_id == "view_jobs":
            self.accept()
            self._host.switch_page(4)
        elif action_id == "view_logs":
            self.accept()
            self._host.switch_page(6)
