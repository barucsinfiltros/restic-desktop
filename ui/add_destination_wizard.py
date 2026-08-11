"""Wizard to add destinations to an existing backup job.

Supports two workflows:
1) Start backing up to the new repositories from now on.
2) Replicate existing snapshots from an existing repository to a newly
   assigned repository (backfill), with optional destination init.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.wizard_dialog import WizardDialog


def _page(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(12)
    heading = QLabel(title)
    heading.setObjectName("sectionCardTitle")
    layout.addWidget(heading)
    help_label = QLabel(subtitle)
    help_label.setObjectName("pageSubtitle")
    help_label.setWordWrap(True)
    layout.addWidget(help_label)
    return page, layout


class AddDestinationWizard(WizardDialog):
    """Add repositories to an existing backup job, optionally backfill snapshots."""

    def __init__(self, parent: QWidget, settings_manager: Any):
        super().__init__(
            "Add Destination / Sync",
            parent,
            finish_text="Continue",
            object_name="addDestinationWizard",
        )
        self.settings_manager = settings_manager

        # Step 1: job selection
        jobs_page, jobs_layout = _page(
            "Choose backup job",
            "Select the backup job you want to extend with new destination repositories.",
        )
        job_form = QVBoxLayout()
        jobs_layout.addLayout(job_form, stretch=1)

        self.job_combo = QComboBox()
        self.job_combo.setMinimumHeight(34)
        self.job_combo.addItem("Select a job", "")
        jobs_layout.addWidget(self.job_combo)
        self._reload_jobs()
        self.job_combo.currentIndexChanged.connect(self._on_job_changed)
        self.add_step("Job", jobs_page, self._validate_job)

        # Step 2: destination repos
        dest_page, dest_layout = _page(
            "Select destinations",
            "Pick one or more repositories to add to the selected backup job.",
        )
        self.dest_list = QListWidget()
        self.dest_list.setObjectName("backupJobList")
        self.dest_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.dest_list.setMinimumHeight(140)
        self.dest_list.setMaximumHeight(200)
        dest_layout.addWidget(self.dest_list, stretch=1)
        self._dest_legend = QLabel()
        self._dest_legend.setObjectName("pageSubtitle")
        self._dest_legend.setWordWrap(True)
        dest_layout.addWidget(self._dest_legend)
        dest_layout.addStretch(1)
        self._update_dest_legend()
        self._reload_repositories()
        self.add_step("Destinations", dest_page, self._validate_destinations)

        # Step 3: mode
        mode_page, mode_layout = _page(
            "Choose sync mode",
            "Either start backing up to the new repositories from now, or replicate existing snapshots to backfill them.",
        )
        self.mode_replicate = QRadioButton("Replicate existing snapshots (backfill)")
        self.mode_backup = QRadioButton("Start backup from now")
        self.mode_backup.setChecked(True)
        mode_layout.addWidget(self.mode_replicate)
        mode_layout.addWidget(self.mode_backup)
        mode_layout.addStretch(1)
        self.mode_replicate.toggled.connect(self._sync_source_step_enabled)
        self.add_step("Mode", mode_page, self._validate_mode)

        # Step 4: source repo (only when replicate chosen)
        source_page, source_layout = _page(
            "Select source repository",
            "Choose where the existing snapshots will be copied from.",
        )
        form_row = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.setMinimumHeight(34)
        form_row.addWidget(self.source_combo, 1)
        source_layout.addLayout(form_row)
        source_layout.addStretch(1)
        self.add_step("Source", source_page, self._validate_source)

        # Step 5: copy options
        options_page, options_layout = _page(
            "Backfill options",
            "Choose how long to allow the copy operation to run, and how to handle destination initialization.",
        )
        self.timeout_hours = QSpinBox()
        self.timeout_hours.setMinimum(0)
        self.timeout_hours.setMaximum(48)
        self.timeout_hours.setValue(6)
        self.timeout_hours.setSingleStep(1)
        self.timeout_hours.setSuffix(" h")
        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Copy timeout:"))
        timeout_row.addWidget(self.timeout_hours, 1)
        options_layout.addLayout(timeout_row)
        options_layout.addWidget(
            QLabel(
                "If the destination repository is not initialized yet, you will be asked to initialize it before copying snapshots."
            )
        )
        options_layout.addStretch(1)
        self.add_step("Options", options_page, self._validate_options)

        # Step 6: review
        review_page, review_layout = _page(
            "Review",
            "Confirm the changes to this job.",
        )
        self.review_label = QLabel()
        self.review_label.setObjectName("wizardReview")
        self.review_label.setWordWrap(True)
        self.review_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        review_layout.addWidget(self.review_label, stretch=1)
        self.add_step("Review", review_page, self._validate_review)
        self.show_step(0)

    def _reload_jobs(self) -> None:
        self.job_combo.blockSignals(True)
        self.job_combo.clear()
        self.job_combo.addItem("Select a job", "")
        for job in self.settings_manager.get("backup_jobs") or []:
            name = str(job.get("name") or "").strip()
            if name:
                self.job_combo.addItem(name, name)
        self.job_combo.blockSignals(False)

    def _reload_repositories(self) -> None:
        """Populate destination picker and visually mark current job repos."""
        self.dest_list.clear()
        job_name = self._current_job_name()
        current_job_repos = set(self._job_repositories(job_name))

        repos = self.settings_manager.get("repositories") or []
        for repo in repos:
            name = str(repo.get("name") or "").strip()
            if not name:
                continue

            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, name)

            # If repo already belongs to the job, highlight it and prevent re-selecting
            # it as a "new destination".
            if name in current_job_repos:
                item.setToolTip("Already part of the selected backup job.")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                item.setForeground(Qt.GlobalColor.darkGray)

            self.dest_list.addItem(item)
        self._update_dest_legend()

    def _update_dest_legend(self) -> None:
        job_name = self._current_job_name()
        current_job_repos = set(self._job_repositories(job_name))
        if not job_name:
            self._dest_legend.setText(
                "Tip: select a job first. Then greyed items are already part of that job."
            )
            return
        existing_count = len(current_job_repos)
        self._dest_legend.setText(
            f"Greyed repos are already in this job ({existing_count}). Select only new destinations."
        )

    def _current_job_name(self) -> str:
        return str(self.job_combo.currentData() or "")

    def _job_repositories(self, job_name: str) -> list[str]:
        job = next(
            (j for j in self.settings_manager.get("backup_jobs") or [] if j.get("name") == job_name),
            None,
        )
        if not job:
            return []
        repos = job.get("repositories") or []
        if not repos and job.get("repository"):
            repos = [job.get("repository")]
        return [r for r in repos if r]

    def _reload_source_choices(self) -> None:
        self.source_combo.clear()
        self.source_combo.addItem("Select a source repository", "")
        job_name = self._current_job_name()
        for repo_name in self._job_repositories(job_name):
            self.source_combo.addItem(repo_name, repo_name)

    def _on_job_changed(self, *_args) -> None:
        self._reload_source_choices()
        self._reload_repositories()
        self._sync_source_step_enabled()
        self._update_review()

    def _selected_destinations(self) -> list[str]:
        dests: list[str] = []
        for item in self.dest_list.selectedItems():
            name = str(item.text() or "").strip()
            if name:
                dests.append(name)
        return dests

    def _sync_source_step_enabled(self) -> None:
        replicate = self.mode_replicate.isChecked()
        self.source_combo.setEnabled(replicate)

    def _validate_job(self) -> str:
        return "" if self._current_job_name() else "Select a backup job."

    def _validate_destinations(self) -> str:
        return (
            "" if self._selected_destinations() else "Select at least one destination repository."
        )

    def _validate_mode(self) -> str:
        # Always valid; just ensure one radio is selected.
        return "" if (self.mode_backup.isChecked() or self.mode_replicate.isChecked()) else "Choose a sync mode."

    def _validate_source(self) -> str:
        if not self.mode_replicate.isChecked():
            return ""
        src = str(self.source_combo.currentData() or "")
        return "" if src else "Select a source repository for replication."

    def _validate_options(self) -> str:
        return ""  # Timeout can be 0 (no timeout)

    def _update_review(self) -> None:
        job_name = self._current_job_name() or "—"
        dests = self._selected_destinations()
        dests_text = ", ".join(dests) if dests else "—"
        if self.mode_replicate.isChecked():
            mode_text = "Replicate existing snapshots (backfill)"
            source_text = str(self.source_combo.currentData() or "—")
        else:
            mode_text = "Start backup from now"
            source_text = "—"
        timeout_text = f"{self.timeout_hours.value()} hours" if self.timeout_hours.value() else "No timeout limit"
        self.review_label.setText(
            f"<b>{job_name}</b><br><br>"
            f"<b>New destinations</b><br>{dests_text}<br><br>"
            f"<b>Mode</b><br>{mode_text}<br>"
            f"<b>Source</b><br>{source_text}<br>"
            f"<b>Timeout</b><br>{timeout_text}"
        )

    def get_action_plan(self) -> dict:
        self._update_review()
        return {
            "job_name": self._current_job_name(),
            "destination_repos": self._selected_destinations(),
            "mode": "replicate" if self.mode_replicate.isChecked() else "backup",
            "source_repo": str(self.source_combo.currentData() or "")
            if self.mode_replicate.isChecked()
            else "",
            "timeout_hours": int(self.timeout_hours.value()),
        }

    def _validate_review(self) -> str:
        # Must keep review always consistent.
        self._update_review()
        # Validate again to show correct errors inline
        return ""

