"""Snapshot Inspector — modern detail view for a single snapshot."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.health import format_relative, _parse_timestamp
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
    val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lay.addWidget(lab, 0)
    lay.addWidget(val, 1)
    return row


def _format_when(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return "—"
    dt = _parse_timestamp(text)
    if dt is None:
        return text.replace("T", " ").split(".")[0].replace("Z", "")
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def match_jobs_for_snapshot(snapshot: dict, jobs: list[dict]) -> list[dict]:
    """Return backup jobs that appear to own this snapshot."""
    from restic_manager import snapshot_matches_backup_job

    matched: list[dict] = []
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        try:
            if snapshot_matches_backup_job(snapshot, job):
                matched.append(job)
        except Exception:
            continue
    return matched


def job_stats_for_snapshots(job: dict, snapshots: list[dict]) -> dict[str, int]:
    """Aggregate snapshot counts / data sizes for one backup job."""
    from restic_manager import snapshot_matches_backup_job

    count = 0
    data_added = 0
    bytes_processed = 0
    files_processed = 0
    for snap in snapshots or []:
        if not isinstance(snap, dict):
            continue
        try:
            if not snapshot_matches_backup_job(snap, job):
                continue
        except Exception:
            continue
        count += 1
        summary = snap.get("summary") or {}
        data_added += _int(summary.get("data_added"))
        bytes_processed += _int(summary.get("total_bytes_processed"))
        files_processed += _int(
            summary.get("total_files_processed")
            or (
                _int(summary.get("files_new"))
                + _int(summary.get("files_changed"))
                + _int(summary.get("files_unmodified"))
            )
        )
    return {
        "count": count,
        "data_added": data_added,
        "bytes_processed": bytes_processed,
        "files_processed": files_processed,
    }


def neighboring_snapshots(
    snapshots: list[dict], current: dict
) -> tuple[Optional[dict], Optional[dict]]:
    """Return (previous older, next newer) by time for the same repo list."""
    if not snapshots or not current:
        return None, None

    def _key(s: dict) -> float:
        dt = _parse_timestamp(s.get("time"))
        return dt.timestamp() if dt is not None else 0.0

    ordered = sorted([s for s in snapshots if isinstance(s, dict)], key=_key)
    cur_id = current.get("id") or ""
    cur_short = current.get("short_id") or str(cur_id)[:8]
    idx = -1
    for i, snap in enumerate(ordered):
        sid = snap.get("short_id") or str(snap.get("id", ""))[:8]
        if (cur_id and snap.get("id") == cur_id) or (cur_short and sid == cur_short):
            idx = i
            break
    if idx < 0:
        return None, None
    prev_snap = ordered[idx - 1] if idx > 0 else None
    next_snap = ordered[idx + 1] if idx + 1 < len(ordered) else None
    return prev_snap, next_snap


class SnapshotInspectorDialog(FramedDialog):
    """Framed inspector for one snapshot — identity, stats, job context, actions."""

    def __init__(
        self,
        host: Any,
        *,
        snapshot: dict,
        repo_name: str = "",
        snapshots: Optional[list[dict]] = None,
        parent=None,
    ):
        short = snapshot.get("short_id") or str(snapshot.get("id", ""))[:8] or "Snapshot"
        super().__init__(
            f"Snapshot · {short}",
            parent or host,
            show_maximize=True,
            show_minimize=False,
            modal=True,
        )
        self._host = host
        self._snapshot = dict(snapshot or {})
        self._repo_name = repo_name or ""
        self._snapshots = list(snapshots or [])
        self.setMinimumSize(920, 760)
        self.resize(980, 820)
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

        header = QHBoxLayout()
        header.setSpacing(12)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Snapshot Inspector")
        title.setObjectName("pageTitle")
        title_col.addWidget(title)
        sub = QLabel(
            "Identity, contents, and backup-job context for this point-in-time backup."
        )
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        title_col.addWidget(sub)
        header.addLayout(title_col, stretch=1)
        if self._repo_name:
            repo_pill = QLabel(self._repo_name)
            repo_pill.setObjectName("pageSubtitle")
            repo_pill.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            header.addWidget(repo_pill, 0, Qt.AlignmentFlag.AlignTop)
        self._content_layout.addLayout(header)

        self._body_host = QVBoxLayout()
        self._body_host.setSpacing(14)
        self._content_layout.addLayout(self._body_host)
        self._content_layout.addStretch(1)
        scroll.setWidget(content)

        footer_bar = QFrame()
        footer_bar.setObjectName("healthFooter")
        footer_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer = QHBoxLayout(footer_bar)
        footer.setContentsMargins(24, 12, 24, 16)
        footer.setSpacing(8)

        footer.addWidget(
            _secondary_btn("Browse Files", self._browse, min_width=120)
        )
        footer.addWidget(
            _secondary_btn("Diff Previous", self._diff, min_width=120)
        )
        footer.addWidget(
            _secondary_btn("Edit Tags", self._edit_tags, min_width=100)
        )
        footer.addWidget(
            _secondary_btn("Copy to Repo", self._copy, min_width=120)
        )
        footer.addWidget(
            _secondary_btn("Forget", self._forget, min_width=100)
        )
        footer.addStretch(1)
        footer.addWidget(_primary_btn("Close", self.accept, min_width=100))
        self.body_layout.addWidget(footer_bar, stretch=0)

        self._rebuild()

    def _theme(self):
        theme_id = themes.resolve_theme_id(self._host.settings_manager.get("theme"))
        return themes.get_app_theme(theme_id)

    def _fmt_bytes(self, value: int) -> str:
        try:
            return self._host.format_bytes(value)
        except Exception:
            return str(value)

    def _jobs_for_repo(self) -> list[dict]:
        jobs = self._host.settings_manager.get("backup_jobs") or []
        out: list[dict] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            repos = job.get("repositories") or []
            if not repos and job.get("repository"):
                repos = [job.get("repository")]
            if self._repo_name and self._repo_name not in repos:
                continue
            out.append(job)
        return out

    def _rebuild(self) -> None:
        while self._body_host.count():
            item = self._body_host.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        snap = self._snapshot
        self._body_host.addWidget(self._build_hero(snap))
        self._body_host.addWidget(self._build_detail_row(snap))
        self._body_host.addWidget(self._build_job_and_related(snap))

    def _build_hero(self, snap: dict) -> QFrame:
        t = self._theme()
        accent = getattr(t, "accent", "#06b6d4")
        short = snap.get("short_id") or str(snap.get("id", ""))[:8] or "—"
        when = _parse_timestamp(snap.get("time"))
        relative = format_relative(when)
        absolute = _format_when(snap.get("time"))

        jobs = match_jobs_for_snapshot(snap, self._jobs_for_repo())
        if len(jobs) == 1:
            job_label = str(jobs[0].get("name") or "Backup job")
        elif len(jobs) > 1:
            job_label = f"{len(jobs)} matching jobs"
        else:
            job_label = "Unassigned"

        summary = snap.get("summary") or {}
        data_added = _int(summary.get("data_added"))
        files_total = _int(
            summary.get("total_files_processed")
            or (
                _int(summary.get("files_new"))
                + _int(summary.get("files_changed"))
                + _int(summary.get("files_unmodified"))
            )
        )
        paths = snap.get("paths") or []

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
        icon.setPixmap(tinted_icon("snapshot.svg", accent, 36).pixmap(36, 36))
        left.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        title = QLabel(short)
        title.setObjectName("healthHeroStatus")
        title.setStyleSheet(f"color: {accent}; font-size: 22px; font-weight: 700;")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_col.addWidget(title)
        msg = QLabel(f"{absolute}  ·  {relative}  ·  {job_label}")
        msg.setObjectName("healthHeroMsg")
        msg.setWordWrap(True)
        text_col.addWidget(msg)
        left.addLayout(text_col, stretch=1)
        row.addLayout(left, stretch=1)

        metrics = QHBoxLayout()
        metrics.setSpacing(18)
        for icon_name, label, value, badge in (
            (
                "snapshot.svg",
                "Data Added",
                self._fmt_bytes(data_added) if data_added else "—",
                "this snapshot",
            ),
            (
                "layers.svg",
                "Files",
                f"{files_total:,}" if files_total else "—",
                "processed",
            ),
            (
                "repository.svg",
                "Paths",
                str(len(paths)),
                "included",
            ),
            (
                "jobs.svg",
                "Backup Job",
                job_label if len(job_label) <= 18 else job_label[:16] + "…",
                "matched",
            ),
        ):
            metrics.addWidget(self._metric_cell(icon_name, label, value, badge))
        row.addLayout(metrics, stretch=0)
        return card

    def _metric_cell(
        self, icon_name: str, label: str, value: str, badge: str
    ) -> QWidget:
        t = self._theme()
        wrap = QWidget()
        wrap.setMinimumWidth(110)
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
        badge_lbl.setObjectName("healthMetricOk")
        col.addWidget(badge_lbl)
        return wrap

    def _detail_card(
        self,
        title: str,
        icon_name: str,
        accent: str,
        rows: list[tuple],
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("healthDetailCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(tinted_icon(icon_name, accent, 16).pixmap(16, 16))
        head.addWidget(ic)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("healthDetailTitle")
        head.addWidget(title_lbl)
        head.addStretch(1)
        lay.addLayout(head)

        for item in rows:
            if len(item) >= 3:
                lay.addWidget(_kv_row(item[0], item[1], value_object=item[2]))
            else:
                lay.addWidget(_kv_row(item[0], item[1]))
        lay.addStretch(1)
        return card

    def _build_detail_row(self, snap: dict) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        tags = snap.get("tags") or []
        tags_txt = ", ".join(str(t) for t in tags) if tags else "None"
        paths = snap.get("paths") or []
        paths_txt = "\n".join(str(p) for p in paths[:6]) if paths else "—"
        if len(paths) > 6:
            paths_txt += f"\n… +{len(paths) - 6} more"

        full_id = str(snap.get("id") or "—")
        identity = self._detail_card(
            "Identity",
            "snapshot.svg",
            "#06b6d4",
            [
                ("Short ID", snap.get("short_id") or full_id[:8]),
                ("Full ID", full_id),
                ("Hostname", str(snap.get("hostname") or "—")),
                ("Username", str(snap.get("username") or "—")),
                ("Tags", tags_txt),
                ("Parent", str(snap.get("parent") or "—")[:8] if snap.get("parent") else "—"),
                ("Restic", str(snap.get("program_version") or "—")),
            ],
        )
        lay.addWidget(identity, stretch=1)

        summary = snap.get("summary") or {}
        files_new = _int(summary.get("files_new"))
        files_changed = _int(summary.get("files_changed"))
        files_unmodified = _int(summary.get("files_unmodified"))
        total_files = _int(summary.get("total_files_processed")) or (
            files_new + files_changed + files_unmodified
        )
        data_added = _int(summary.get("data_added"))
        total_bytes = _int(summary.get("total_bytes_processed"))

        contents = self._detail_card(
            "Contents",
            "layers.svg",
            "#a855f7",
            [
                ("Paths", paths_txt),
                ("Files New", f"{files_new:,}"),
                ("Files Changed", f"{files_changed:,}"),
                ("Files Unmodified", f"{files_unmodified:,}"),
                ("Total Files", f"{total_files:,}" if total_files else "—"),
                ("Data Added", self._fmt_bytes(data_added) if data_added else "—"),
                (
                    "Bytes Processed",
                    self._fmt_bytes(total_bytes) if total_bytes else "—",
                ),
            ],
        )
        lay.addWidget(contents, stretch=1)
        return row

    def _build_job_and_related(self, snap: dict) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        repo_jobs = self._jobs_for_repo()
        matched = match_jobs_for_snapshot(snap, repo_jobs)

        job_rows: list[tuple] = []
        if not repo_jobs:
            job_rows.append(("Jobs in repo", "None configured"))
        elif not matched:
            job_rows.append(("Matched job", "None (paths/tags don't match)"))
        else:
            for job in matched:
                stats = job_stats_for_snapshots(job, self._snapshots)
                name = str(job.get("name") or "Unnamed")
                job_rows.append((f"Job · {name}", f"{stats['count']} snapshot(s)"))
                job_rows.append(
                    (
                        "  Total data added",
                        self._fmt_bytes(stats["data_added"])
                        if stats["data_added"]
                        else "—",
                    )
                )
                job_rows.append(
                    (
                        "  Bytes processed",
                        self._fmt_bytes(stats["bytes_processed"])
                        if stats["bytes_processed"]
                        else "—",
                    )
                )
                job_rows.append(
                    (
                        "  Files processed",
                        f"{stats['files_processed']:,}"
                        if stats["files_processed"]
                        else "—",
                    )
                )

        # Also show other jobs on this repo as a compact fleet view
        other = [j for j in repo_jobs if j not in matched]
        if other:
            job_rows.append(("Other jobs on repo", str(len(other))))
            for job in other[:4]:
                stats = job_stats_for_snapshots(job, self._snapshots)
                name = str(job.get("name") or "Unnamed")
                size = (
                    self._fmt_bytes(stats["data_added"])
                    if stats["data_added"]
                    else "—"
                )
                job_rows.append(
                    (f"  {name}", f"{stats['count']} snaps · {size} added")
                )
            if len(other) > 4:
                job_rows.append(("  …", f"+{len(other) - 4} more"))

        jobs_card = self._detail_card(
            "Backup Job Stats",
            "jobs.svg",
            "#3b82f6",
            job_rows or [("Jobs", "—")],
        )
        lay.addWidget(jobs_card, stretch=1)

        prev_snap, next_snap = neighboring_snapshots(self._snapshots, snap)

        def _snap_line(s: Optional[dict]) -> str:
            if not s:
                return "—"
            sid = s.get("short_id") or str(s.get("id", ""))[:8]
            when = format_relative(_parse_timestamp(s.get("time")))
            return f"{sid}  ·  {when}"

        related = self._detail_card(
            "Related",
            "restore.svg",
            "#22c55e",
            [
                ("Previous", _snap_line(prev_snap)),
                ("Next", _snap_line(next_snap)),
                ("In repository", self._repo_name or "—"),
                ("Loaded snapshots", str(len(self._snapshots))),
            ],
        )
        lay.addWidget(related, stretch=1)
        return row

    def _ensure_row_selected(self) -> None:
        """Best-effort: select this snapshot in the table before host actions."""
        table = getattr(self._host, "snapshots_table", None)
        if table is None:
            return
        cur_id = self._snapshot.get("id") or ""
        cur_short = self._snapshot.get("short_id") or str(cur_id)[:8]
        for row in range(table.rowCount()):
            from ui.snapshots import snapshot_data_from_row

            data = snapshot_data_from_row(table, row)
            if not data:
                continue
            if (cur_id and data.get("id") == cur_id) or (
                cur_short
                and (data.get("short_id") or str(data.get("id", ""))[:8]) == cur_short
            ):
                table.selectRow(row)
                break

    def _browse(self) -> None:
        self._ensure_row_selected()
        self.accept()
        self._host.browse_snapshot_content()

    def _diff(self) -> None:
        self._ensure_row_selected()
        self.accept()
        self._host.diff_snapshots()

    def _edit_tags(self) -> None:
        self._ensure_row_selected()
        self.accept()
        self._host.edit_snapshot_tags()

    def _copy(self) -> None:
        self._ensure_row_selected()
        self.accept()
        self._host.copy_snapshot_to_repository()

    def _forget(self) -> None:
        self._ensure_row_selected()
        self.accept()
        self._host.forget_snapshot()
