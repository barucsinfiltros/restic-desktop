"""Repository health scoring and recommendations."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _parse_timestamp(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text or text in ("—", "Never", "None"):
        return None
    candidates = [
        text,
        text.replace("Z", "+00:00"),
        text.replace(" ", "T", 1),
    ]
    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def format_relative(dt: Optional[datetime], *, never: str = "Never") -> str:
    if dt is None:
        return never
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = int((now - dt.astimezone(timezone.utc)).total_seconds())
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        mins = seconds // 60
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = seconds // 86400
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def format_due_in(dt: Optional[datetime], interval_hours: int) -> str:
    """Human label for when the next check/test is due."""
    if dt is None:
        return "Now"
    try:
        hours = max(1, int(interval_hours))
    except (TypeError, ValueError):
        hours = 24
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    due = dt.astimezone(timezone.utc).timestamp() + hours * 3600
    remaining = int(due - now.timestamp())
    if remaining <= 0:
        return "Overdue"
    if remaining < 3600:
        mins = max(1, remaining // 60)
        return f"In {mins} minute{'s' if mins != 1 else ''}"
    if remaining < 86400:
        hrs = remaining // 3600
        return f"In {hrs} hour{'s' if hrs != 1 else ''}"
    days = remaining // 86400
    return f"In {days} day{'s' if days != 1 else ''}"


def hours_since(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt.astimezone(timezone.utc)).total_seconds() / 3600.0


def days_since(dt: Optional[datetime]) -> Optional[float]:
    h = hours_since(dt)
    return None if h is None else h / 24.0


@dataclass
class HealthThresholds:
    backup_overdue_hours: int = 36
    backup_overdue_value: int = 36
    backup_overdue_unit: str = "hours"  # hours | days | months
    check_interval_hours: int = 30 * 24
    check_interval_value: int = 30
    check_interval_unit: str = "days"
    restore_test_interval_hours: int = 30 * 24
    restore_test_interval_value: int = 30
    restore_test_interval_unit: str = "days"
    default_check_level: str = "quick"  # quick | partial | full
    restore_test_max_files: int = 5

    @property
    def check_interval_days(self) -> int:
        return max(1, (int(self.check_interval_hours) + 23) // 24)

    @property
    def restore_test_interval_days(self) -> int:
        return max(1, (int(self.restore_test_interval_hours) + 23) // 24)

    @staticmethod
    def amount_to_hours(value: int, unit: str) -> int:
        """Convert a user-facing amount into hours."""
        try:
            amount = max(1, int(value))
        except (TypeError, ValueError):
            amount = 1
        u = (unit or "hours").strip().lower()
        if u == "days":
            return amount * 24
        if u in ("months", "month"):
            return amount * 24 * 30  # approximate calendar month
        return amount

    # Back-compat alias
    overdue_to_hours = amount_to_hours

    @staticmethod
    def resolve_amount_setting(
        settings: Any,
        *,
        value_key: str,
        unit_key: str,
        legacy_hours_key: str = "",
        legacy_days_key: str = "",
        default_value: int = 30,
        default_unit: str = "days",
    ) -> tuple[int, str, int]:
        """Return (value, unit, hours) from settings with legacy fallbacks."""

        def _get(key: str, default=None):
            if hasattr(settings, "get"):
                return settings.get(key)
            return default

        unit = str(_get(unit_key) or "").strip().lower()
        raw_value = _get(value_key)
        if unit not in ("hours", "days", "months"):
            unit = ""
        try:
            value = int(raw_value) if raw_value is not None else None
        except (TypeError, ValueError):
            value = None

        if value is not None and unit:
            hours = HealthThresholds.amount_to_hours(value, unit)
            return max(1, value), unit, hours

        if legacy_hours_key:
            try:
                hours = int(_get(legacy_hours_key) or 0)
            except (TypeError, ValueError):
                hours = 0
            if hours > 0:
                return hours, "hours", hours

        if legacy_days_key:
            try:
                days = int(_get(legacy_days_key) or default_value)
            except (TypeError, ValueError):
                days = default_value
            days = max(1, days)
            return days, "days", days * 24

        hours = HealthThresholds.amount_to_hours(default_value, default_unit)
        return default_value, default_unit, hours

    @staticmethod
    def resolve_overdue_setting(settings: Any) -> tuple[int, str, int]:
        return HealthThresholds.resolve_amount_setting(
            settings,
            value_key="health_backup_overdue_value",
            unit_key="health_backup_overdue_unit",
            legacy_hours_key="health_backup_overdue_hours",
            default_value=36,
            default_unit="hours",
        )

    def amount_label(self, value: int, unit: str) -> str:
        n = max(1, int(value))
        u = (unit or "hours").lower()
        if u == "days":
            return f"{n} day{'s' if n != 1 else ''}"
        if u == "months":
            return f"{n} month{'s' if n != 1 else ''}"
        return f"{n} hour{'s' if n != 1 else ''}"

    def overdue_label(self) -> str:
        return self.amount_label(self.backup_overdue_value, self.backup_overdue_unit)

    @classmethod
    def from_settings(cls, settings: Any) -> "HealthThresholds":
        def _int(key: str, default: int) -> int:
            try:
                raw = settings.get(key) if hasattr(settings, "get") else None
                return int(raw if raw is not None else default)
            except (TypeError, ValueError):
                return default

        level = "quick"
        if hasattr(settings, "get"):
            level = str(settings.get("health_default_check_level") or "quick")
        level = (level or "quick").strip().lower()
        if level not in ("quick", "partial", "full"):
            level = "quick"

        overdue_value, overdue_unit, overdue_hours = cls.resolve_overdue_setting(settings)
        check_value, check_unit, check_hours = cls.resolve_amount_setting(
            settings,
            value_key="health_check_interval_value",
            unit_key="health_check_interval_unit",
            legacy_days_key="health_check_interval_days",
            default_value=30,
            default_unit="days",
        )
        restore_value, restore_unit, restore_hours = cls.resolve_amount_setting(
            settings,
            value_key="health_restore_test_interval_value",
            unit_key="health_restore_test_interval_unit",
            legacy_days_key="health_restore_test_interval_days",
            default_value=30,
            default_unit="days",
        )
        return cls(
            backup_overdue_hours=max(1, overdue_hours),
            backup_overdue_value=max(1, overdue_value),
            backup_overdue_unit=overdue_unit,
            check_interval_hours=max(1, check_hours),
            check_interval_value=max(1, check_value),
            check_interval_unit=check_unit,
            restore_test_interval_hours=max(1, restore_hours),
            restore_test_interval_value=max(1, restore_value),
            restore_test_interval_unit=restore_unit,
            default_check_level=level,
            restore_test_max_files=max(1, min(50, _int("health_restore_test_max_files", 5))),
        )


@dataclass
class Recommendation:
    kind: str  # check | restore | jobs | praise | warning
    title: str
    detail: str
    action: str = ""  # button label, empty = no button
    action_id: str = ""  # run_check | run_restore_test | view_jobs


@dataclass
class HealthEvent:
    kind: str  # ok | warn | err
    title: str
    detail: str
    when: str


@dataclass
class RepoHealthReport:
    repo_name: str
    status: str  # healthy | warning | critical | unknown
    status_label: str
    status_message: str
    score: int
    score_label: str

    last_backup: Optional[datetime] = None
    last_backup_label: str = "Never"
    last_backup_status: str = "Unknown"

    last_check: Optional[datetime] = None
    last_check_label: str = "Never"
    last_check_result: str = "Not checked"
    next_check_label: str = "Now"
    check_type: str = ""

    last_restore_test: Optional[datetime] = None
    last_restore_test_label: str = "Never"
    last_restore_test_result: str = "Not tested"
    restore_files: int = 0
    restore_bytes: int = 0
    next_restore_label: str = "Now"

    snapshot_count: int = 0
    total_size: int = 0
    job_count: int = 0
    failed_jobs: int = 0
    overdue_jobs: int = 0
    next_scheduled_label: str = "—"

    recommendations: list[Recommendation] = field(default_factory=list)
    events: list[HealthEvent] = field(default_factory=list)


def _score_label(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 25:
        return "Poor"
    return "Critical"


def compute_repo_health(
    repo: dict,
    *,
    thresholds: HealthThresholds,
    last_backup_raw: str = "",
    snapshot_count: int = 0,
    total_size: int = 0,
    jobs: Optional[list[dict]] = None,
    events: Optional[list[HealthEvent]] = None,
) -> RepoHealthReport:
    """Score one repository from stored metadata + job schedule info."""
    name = str(repo.get("name") or "Repository")
    jobs = jobs or []
    last_backup = _parse_timestamp(last_backup_raw) or _parse_timestamp(
        repo.get("last_backup")
    )
    last_check = _parse_timestamp(repo.get("last_integrity_check"))
    check_result_raw = str(repo.get("last_integrity_result") or "").strip().lower()
    check_type = str(repo.get("last_integrity_type") or "").strip().lower()
    last_restore = _parse_timestamp(repo.get("last_restore_test"))
    restore_result_raw = str(repo.get("last_restore_test_result") or "").strip().lower()
    try:
        restore_files = int(repo.get("last_restore_test_files") or 0)
    except (TypeError, ValueError):
        restore_files = 0
    try:
        restore_bytes = int(repo.get("last_restore_test_bytes") or 0)
    except (TypeError, ValueError):
        restore_bytes = 0

    job_count = len(jobs)
    failed_jobs = 0
    overdue_jobs = 0
    next_scheduled_label = "—"
    # Best-effort next schedule from job metadata (ISO or empty)
    next_candidates: list[datetime] = []
    for job in jobs:
        last_status = str(job.get("last_status") or job.get("status") or "").lower()
        if last_status in ("failed", "error", "fail"):
            failed_jobs += 1
        # overdue: enabled schedule + last backup older than threshold
        enabled = bool(job.get("schedule_enabled") or (job.get("schedule") or {}).get("enabled"))
        if enabled and last_backup is not None:
            age_h = hours_since(last_backup)
            if age_h is not None and age_h > thresholds.backup_overdue_hours:
                overdue_jobs += 1
        nxt = _parse_timestamp(job.get("next_run") or "")
        if nxt is not None:
            next_candidates.append(nxt)

    if next_candidates:
        soonest = min(next_candidates)
        now = datetime.now(timezone.utc)
        if soonest.tzinfo is None:
            soonest = soonest.replace(tzinfo=timezone.utc)
        delta = int((soonest.astimezone(timezone.utc) - now).total_seconds())
        if delta <= 0:
            next_scheduled_label = "Due now"
        elif delta < 3600:
            next_scheduled_label = f"In {max(1, delta // 60)} minutes"
        elif delta < 86400:
            next_scheduled_label = f"In {delta // 3600} hours"
        else:
            next_scheduled_label = f"In {delta // 86400} days"
    elif job_count:
        next_scheduled_label = "See schedule"

    # ── Score ────────────────────────────────────────────────────
    score = 100
    backup_overdue = False
    check_overdue = False
    restore_overdue = False
    check_failed = check_result_raw in ("failed", "fail", "error")
    restore_failed = restore_result_raw in ("failed", "fail", "error")
    check_passed = check_result_raw in ("passed", "ok", "success", "healthy")
    restore_passed = restore_result_raw in ("passed", "ok", "success")

    if last_backup is None:
        score -= 40
        last_backup_status = "Never"
    else:
        age_h = hours_since(last_backup) or 0
        if age_h > thresholds.backup_overdue_hours:
            backup_overdue = True
            score -= 25
            last_backup_status = "Overdue"
        else:
            last_backup_status = "Successful"

    if failed_jobs:
        score -= min(30, failed_jobs * 15)
    if overdue_jobs:
        score -= min(20, overdue_jobs * 10)

    if last_check is None:
        score -= 15
        check_result_label = "Not checked"
        check_overdue = True
    else:
        age_h = hours_since(last_check) or 0
        if check_failed:
            score -= 35
            check_result_label = "Failed"
        elif age_h > thresholds.check_interval_hours:
            check_overdue = True
            score -= 10
            check_result_label = "Passed" if check_passed else "Completed"
        else:
            check_result_label = "Passed" if check_passed else ("Failed" if check_failed else "Completed")

    if last_restore is None:
        score -= 10
        restore_result_label = "Not tested"
        restore_overdue = True
    else:
        age_h = hours_since(last_restore) or 0
        if restore_failed:
            score -= 20
            restore_result_label = "Failed"
        elif age_h > thresholds.restore_test_interval_hours:
            restore_overdue = True
            score -= 5
            restore_result_label = "Passed" if restore_passed else "Completed"
        else:
            restore_result_label = "Passed" if restore_passed else ("Failed" if restore_failed else "Completed")

    score = max(0, min(100, score))

    check_due = last_check is None or check_overdue or check_failed
    restore_due = last_restore is None or restore_overdue or restore_failed
    trust_ok = (
        last_check is not None
        and check_passed
        and not check_overdue
        and not check_failed
        and last_restore is not None
        and restore_passed
        and not restore_overdue
        and not restore_failed
    )

    # Overall status is driven by integrity / restore trust and job failures —
    # not by backup age alone (that is shown on the Last Backup metric).
    if check_failed or restore_failed or (last_backup is None and job_count) or score < 40:
        status = "critical"
        status_label = "At Risk"
        if check_failed or restore_failed:
            status_message = "A verification check failed. Investigate before trusting this repository."
        elif last_backup is None:
            status_message = "No successful backup found for this repository yet."
        else:
            status_message = "One or more health checks need attention."
    elif check_due or restore_due or failed_jobs or overdue_jobs:
        status = "warning"
        status_label = "Needs Attention"
        parts = []
        if check_due:
            parts.append("integrity check")
        if restore_due:
            parts.append("restore test")
        if failed_jobs:
            parts.append("failed jobs")
        if overdue_jobs:
            parts.append("overdue jobs")
        if parts:
            status_message = (
                "Recommended actions are due: " + ", ".join(parts) + "."
            )
        else:
            status_message = "Backups may still work, but recommended checks are due."
    elif last_backup is None and not job_count:
        status = "unknown"
        status_label = "Unknown"
        status_message = "No backup history yet for this repository."
    else:
        status = "healthy"
        status_label = "Healthy"
        if backup_overdue:
            status_message = (
                "Integrity and restore checks passed. "
                "Last backup is older than your freshness threshold."
            )
        elif trust_ok:
            status_message = "Everything looks good. Checks passed and backups are up to date."
        else:
            status_message = "Repository health looks good."

    recs: list[Recommendation] = []
    if last_check is None or check_overdue or check_failed:
        detail = (
            "Integrity has never been verified."
            if last_check is None
            else (
                "Last check failed."
                if check_failed
                else f"Last check was {format_relative(last_check)}."
            )
        )
        recs.append(
            Recommendation(
                "check",
                "Run repository check",
                detail,
                "Run Check",
                "run_check",
            )
        )
    if last_restore is None or restore_overdue or restore_failed:
        detail = (
            "Recommended every "
            f"{thresholds.amount_label(thresholds.restore_test_interval_value, thresholds.restore_test_interval_unit)}."
            if last_restore is None
            else (
                "Last restore test failed."
                if restore_failed
                else f"Last restore test was {format_relative(last_restore)}."
            )
        )
        recs.append(
            Recommendation(
                "restore",
                "Run restore verification",
                detail,
                "Verify Restore",
                "run_restore_test",
            )
        )
    if failed_jobs:
        recs.append(
            Recommendation(
                "jobs",
                "Review failed backup jobs",
                f"{failed_jobs} job(s) reported a failure.",
                "View Jobs",
                "view_jobs",
            )
        )
    if backup_overdue and last_backup is not None:
        recs.append(
            Recommendation(
                "warning",
                "Backup is overdue",
                f"Last backup was {format_relative(last_backup)} "
                f"(threshold {thresholds.overdue_label()}).",
                "View Jobs",
                "view_jobs",
            )
        )
    if status == "healthy" and not recs:
        recs.append(
            Recommendation(
                "praise",
                "Good job!",
                "Your backups are healthy and up to date.",
            )
        )
    elif not recs and status != "healthy":
        recs.append(
            Recommendation(
                "warning",
                "Review repository health",
                status_message,
                "View Jobs",
                "view_jobs",
            )
        )

    return RepoHealthReport(
        repo_name=name,
        status=status,
        status_label=status_label,
        status_message=status_message,
        score=score,
        score_label=_score_label(score),
        last_backup=last_backup,
        last_backup_label=format_relative(last_backup),
        last_backup_status=last_backup_status,
        last_check=last_check,
        last_check_label=format_relative(last_check),
        last_check_result=check_result_label,
        next_check_label=format_due_in(last_check, thresholds.check_interval_hours),
        check_type=check_type,
        last_restore_test=last_restore,
        last_restore_test_label=format_relative(last_restore),
        last_restore_test_result=restore_result_label,
        restore_files=restore_files,
        restore_bytes=restore_bytes,
        next_restore_label=format_due_in(
            last_restore, thresholds.restore_test_interval_hours
        ),
        snapshot_count=snapshot_count,
        total_size=total_size,
        job_count=job_count,
        failed_jobs=failed_jobs,
        overdue_jobs=overdue_jobs,
        next_scheduled_label=next_scheduled_label,
        recommendations=recs,
        events=list(events or []),
    )


def _short_issue(report: RepoHealthReport) -> str:
    """Compact reason for dashboard Status subtitle."""
    for rec in report.recommendations:
        if rec.kind == "praise":
            continue
        if rec.kind == "check":
            return "check due" if "fail" not in rec.title.lower() else "check failed"
        if rec.kind == "restore":
            return "restore due" if "fail" not in rec.detail.lower() else "restore failed"
        if rec.kind == "jobs":
            return "failed jobs"
        if rec.kind == "warning" and "backup" in rec.title.lower():
            return "backup overdue"
        if rec.title:
            return rec.title[:28]
    msg = (report.status_message or "").strip()
    if msg:
        return msg.split(".")[0][:36]
    return report.status_label


def compute_overall_status(
    reports: list[RepoHealthReport],
) -> tuple[str, str, str, str, list[tuple[str, str]], str, str]:
    """
    Aggregate dashboard Status card.

    Returns
    -------
    status_key, value_label, subtitle,
    tip_title, tip_rows [(name, issue), ...], tip_footer, focus_repo_name
    """
    if not reports:
        return (
            "unknown",
            "—",
            "No repositories",
            "No repositories",
            [],
            "Add a repository to get started.",
            "",
        )

    order = {"critical": 0, "warning": 1, "unknown": 2, "healthy": 3}
    worst = min(reports, key=lambda r: (order.get(r.status, 9), r.score))
    problem_repos = [r for r in reports if r.status in ("warning", "critical")]

    if worst.status == "healthy":
        weakest = min(reports, key=lambda r: r.score)
        subtitle = f"{weakest.repo_name} · {weakest.score}/100"
        rows = [
            (r.repo_name, f"{r.score}/100")
            for r in sorted(reports, key=lambda x: x.score)[:8]
        ]
        return (
            "healthy",
            "Healthy",
            subtitle,
            "Repository health",
            rows,
            "Click to open Repository Health.",
            weakest.repo_name,
        )

    if worst.status == "unknown" and not problem_repos:
        return (
            "unknown",
            "Unknown",
            f"{worst.repo_name} · no history",
            "No backup history",
            [(worst.repo_name, "no history")],
            worst.status_message or "No backup history yet.",
            worst.repo_name,
        )

    issue = _short_issue(worst)
    if len(problem_repos) <= 1:
        subtitle = f"{worst.repo_name} · {issue}"
    else:
        subtitle = f"{worst.repo_name} +{len(problem_repos) - 1} more"

    tip_title = (
        f"{len(problem_repos)} repository needs attention"
        if len(problem_repos) == 1
        else f"{len(problem_repos)} repositories need attention"
    )
    tip_rows = [
        (r.repo_name, _short_issue(r))
        for r in sorted(problem_repos, key=lambda x: (order.get(x.status, 9), x.score))
    ]
    return (
        worst.status if worst.status in ("warning", "critical") else "warning",
        "At Risk" if worst.status == "critical" else "Warning",
        subtitle,
        tip_title,
        tip_rows,
        "Click to open Repository Health.",
        worst.repo_name,
    )
