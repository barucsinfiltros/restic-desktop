"""Guided backup-job creation wizard."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTimeEdit,
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


class BackupWizard(WizardDialog):
    """Create a normal saved backup job through a focused four-step flow."""

    def __init__(self, parent, settings_manager):
        super().__init__(
            "New Backup",
            parent,
            finish_text="Save Backup",
            object_name="backupWizard",
        )
        self.settings_manager = settings_manager

        basics, basics_layout = _page(
            "Backup details",
            "Name this backup, then choose where to store it from your existing "
            "repositories — or create a new one.",
        )
        form = QFormLayout()
        form.setSpacing(12)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Daily Documents")
        self.name_input.setMinimumHeight(34)
        form.addRow("Backup name", self.name_input)
        basics_layout.addLayout(form)

        repos_header = QHBoxLayout()
        repos_header.setSpacing(8)
        repos_label = QLabel("Existing repositories")
        repos_label.setObjectName("sectionCardTitle")
        repos_header.addWidget(repos_label)
        repos_header.addStretch(1)
        new_repo_btn = QPushButton("New Repository")
        new_repo_btn.setObjectName("dialogSecondary")
        new_repo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_repo_btn.setToolTip("Create or add a repository, then select it for this backup")
        new_repo_btn.clicked.connect(self._create_repository)
        repos_header.addWidget(new_repo_btn)
        basics_layout.addLayout(repos_header)

        repos_hint = QLabel(
            "Select one or more destinations already configured in Restic Desktop."
        )
        repos_hint.setObjectName("pageSubtitle")
        repos_hint.setWordWrap(True)
        basics_layout.addWidget(repos_hint)

        self.repos_list = QListWidget()
        self.repos_list.setObjectName("backupJobList")
        self.repos_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.repos_empty_label = QLabel(
            "No repositories yet. Click New Repository to create one."
        )
        self.repos_empty_label.setObjectName("pageSubtitle")
        self.repos_empty_label.setWordWrap(True)
        self.repos_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        basics_layout.addWidget(self.repos_list, stretch=1)
        basics_layout.addWidget(self.repos_empty_label)
        self._reload_repositories()
        self.add_step("Details", basics, self._validate_basics)

        sources, sources_layout = _page(
            "Source folders",
            "Choose the folders that should be included in this backup.",
        )
        self.paths_list = QListWidget()
        self.paths_list.setObjectName("backupJobList")
        sources_layout.addWidget(self.paths_list, stretch=1)
        path_actions = QHBoxLayout()
        add_path = QPushButton("Add Folder")
        add_path.setObjectName("dialogPrimary")
        add_path.clicked.connect(self._add_path)
        remove_path = QPushButton("Remove")
        remove_path.setObjectName("dialogSecondary")
        remove_path.clicked.connect(self._remove_path)
        path_actions.addWidget(add_path)
        path_actions.addWidget(remove_path)
        path_actions.addStretch(1)
        sources_layout.addLayout(path_actions)
        self.add_step("Folders", sources, self._validate_paths)

        schedule, schedule_layout = _page(
            "Schedule",
            "Run manually, or ask the operating system to run this backup automatically.",
        )
        self.schedule_enabled = QCheckBox("Enable automatic scheduling")
        schedule_layout.addWidget(self.schedule_enabled)
        self.schedule_fields = QWidget()
        schedule_form = QFormLayout(self.schedule_fields)
        schedule_form.setSpacing(10)
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems(["Daily", "Weekly", "Monthly"])
        schedule_form.addRow("Frequency", self.frequency_combo)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(2, 0))
        schedule_form.addRow("Time", self.time_edit)

        self.days_widget = QWidget()
        days_row = QHBoxLayout(self.days_widget)
        days_row.setContentsMargins(0, 0, 0, 0)
        days_row.setSpacing(5)
        self.day_checks: dict[str, QCheckBox] = {}
        for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
            check = QCheckBox(day)
            self.day_checks[day] = check
            days_row.addWidget(check)
        schedule_form.addRow("Days", self.days_widget)

        self.day_of_month = QSpinBox()
        self.day_of_month.setRange(1, 28)
        schedule_form.addRow("Day of month", self.day_of_month)
        schedule_layout.addWidget(self.schedule_fields)
        schedule_layout.addStretch(1)
        self.schedule_enabled.toggled.connect(self._update_schedule_fields)
        self.frequency_combo.currentTextChanged.connect(self._update_schedule_fields)
        self._update_schedule_fields()
        self.add_step("Schedule", schedule, self._validate_schedule)

        review, review_layout = _page(
            "Review",
            "Confirm the backup job before saving it.",
        )
        self.review_label = QLabel()
        self.review_label.setObjectName("wizardReview")
        self.review_label.setWordWrap(True)
        self.review_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        review_layout.addWidget(self.review_label, stretch=1)
        self.run_now_check = QCheckBox("Run this backup now after saving")
        review_layout.addWidget(self.run_now_check)
        self.add_step("Review", review)

    def _reload_repositories(
        self,
        *,
        keep_selected: set[str] | None = None,
        prefer_select: str | None = None,
    ) -> None:
        """Refresh the destination list from settings."""
        selected = keep_selected
        if selected is None:
            selected = {
                item.text() for item in self.repos_list.selectedItems()
            }
        if prefer_select:
            selected = set(selected) | {prefer_select}

        self.repos_list.clear()
        names: list[str] = []
        for repo in self.settings_manager.get("repositories") or []:
            name = str(repo.get("name") or "").strip()
            if name:
                names.append(name)
                self.repos_list.addItem(name)

        for i in range(self.repos_list.count()):
            item = self.repos_list.item(i)
            if item and item.text() in selected:
                item.setSelected(True)

        empty = not names
        self.repos_list.setVisible(not empty)
        self.repos_empty_label.setVisible(empty)

    def _create_repository(self) -> None:
        """Open the standard add-repository flow and select the new repo."""
        host = self.parent()
        if host is None or not hasattr(host, "add_repository"):
            return
        previously = {item.text() for item in self.repos_list.selectedItems()}

        def on_added(name: str) -> None:
            self._reload_repositories(
                keep_selected=previously | {name},
                prefer_select=name,
            )

        host.add_repository(on_added=on_added)

    def _add_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Folder to Back Up")
        if path and not self.paths_list.findItems(
            path, Qt.MatchFlag.MatchFixedString
        ):
            self.paths_list.addItem(path)

    def _remove_path(self) -> None:
        row = self.paths_list.currentRow()
        if row >= 0:
            self.paths_list.takeItem(row)

    def _validate_basics(self) -> str:
        name = self.name_input.text().strip()
        if not name:
            return "Enter a backup name."
        if (
            any(char in name for char in '<>:"/\\|?*`$')
            or any(ord(char) < 32 for char in name)
        ):
            return "The backup name contains characters Windows cannot use."
        if not self.repos_list.selectedItems():
            if self.repos_list.count() == 0:
                return "Create or add a repository, then select it."
            return "Select at least one existing repository."
        return ""

    def _validate_paths(self) -> str:
        return "" if self.paths_list.count() else "Add at least one source folder."

    def _validate_schedule(self) -> str:
        if (
            self.schedule_enabled.isChecked()
            and len(self.repos_list.selectedItems()) > 1
        ):
            return (
                "Scheduled backups currently support one repository. "
                "Select one repository or leave scheduling disabled."
            )
        if (
            self.schedule_enabled.isChecked()
            and self.frequency_combo.currentText() == "Weekly"
            and not any(check.isChecked() for check in self.day_checks.values())
        ):
            return "Select at least one weekday."
        return ""

    def _update_schedule_fields(self) -> None:
        enabled = self.schedule_enabled.isChecked()
        frequency = self.frequency_combo.currentText()
        self.schedule_fields.setEnabled(enabled)
        self.days_widget.setVisible(enabled and frequency == "Weekly")
        self.day_of_month.setVisible(enabled and frequency == "Monthly")

    def on_step_changed(self, index: int) -> None:
        if index == 3:
            job = self.get_job_data()
            schedule = job["schedule"]
            if schedule.get("enabled"):
                schedule_text = (
                    f"{schedule['frequency'].capitalize()} at {schedule['time']}"
                )
            else:
                schedule_text = "Manual"
            paths = "<br>".join(f"• {path}" for path in job["paths"])
            repos = ", ".join(job["repositories"])
            self.review_label.setText(
                f"<b>{job['name']}</b><br><br>"
                f"<b>Repositories</b><br>{repos}<br><br>"
                f"<b>Folders</b><br>{paths}<br><br>"
                f"<b>Schedule</b><br>{schedule_text}"
            )

    def get_job_data(self) -> dict:
        selected_days = [
            day for day, check in self.day_checks.items() if check.isChecked()
        ]
        if self.schedule_enabled.isChecked():
            schedule = {
                "enabled": True,
                "frequency": self.frequency_combo.currentText().lower(),
                "time": self.time_edit.time().toString("HH:mm"),
                "days": selected_days,
                "day_of_month": self.day_of_month.value(),
                "run_if_missed": True,
                "pause_after_completion": False,
                "last_run": None,
            }
        else:
            schedule = {"enabled": False}

        return {
            "name": self.name_input.text().strip(),
            "repositories": [
                item.text() for item in self.repos_list.selectedItems()
            ],
            "paths": [
                self.paths_list.item(i).text()
                for i in range(self.paths_list.count())
            ],
            "tags": [],
            "exclude_patterns": [],
            "exclude_caches": True,
            "pack_size": 16,
            "one_file_system": False,
            "timeout": 7200,
            "exclude_if_present": "",
            "compression": "auto",
            "no_cache": False,
            "ignore_inode": False,
            "skip_if_unchanged": True,
            "schedule": schedule,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def run_now(self) -> bool:
        return self.run_now_check.isChecked()

