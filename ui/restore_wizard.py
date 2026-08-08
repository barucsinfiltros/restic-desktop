"""Guided repository restore wizard."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
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


class RestoreWizard(WizardDialog):
    """Collect a restore request while delegating loading/browsing to the host."""

    def __init__(self, host):
        super().__init__(
            "Restore Files",
            host,
            finish_text="Start Restore",
            object_name="restoreWizard",
        )
        self.host = host
        self._snapshots: list[dict] = []
        self._catalog_request = 0

        source, source_layout = _page(
            "Choose a snapshot",
            "Select the repository and backup snapshot you want to restore.",
        )
        source_form = QFormLayout()
        source_form.setSpacing(12)
        self.repo_combo = QComboBox()
        self.repo_combo.addItem("Select a repository", "")
        for repo in host.settings_manager.get("repositories") or []:
            name = str(repo.get("name") or "").strip()
            if name:
                self.repo_combo.addItem(name, name)
        source_form.addRow("Repository", self.repo_combo)
        self.snapshot_combo = QComboBox()
        self.snapshot_combo.addItem("Select a repository first", "")
        source_form.addRow("Snapshot", self.snapshot_combo)
        source_layout.addLayout(source_form)
        self.catalog_status = QLabel("")
        self.catalog_status.setObjectName("pageSubtitle")
        source_layout.addWidget(self.catalog_status)
        source_layout.addStretch(1)
        self.repo_combo.currentIndexChanged.connect(self._load_snapshots)
        self.add_step("Snapshot", source, self._validate_source)

        files, files_layout = _page(
            "Choose what to restore",
            "Restore the entire snapshot, or browse and select specific files and folders.",
        )
        self.entire_snapshot = QRadioButton("Restore the entire snapshot")
        self.selected_paths = QRadioButton("Restore selected files and folders")
        self.entire_snapshot.setChecked(True)
        files_layout.addWidget(self.entire_snapshot)
        files_layout.addWidget(self.selected_paths)
        self.paths_list = QListWidget()
        self.paths_list.setObjectName("backupJobList")
        self.paths_list.setEnabled(False)
        files_layout.addWidget(self.paths_list, stretch=1)
        file_actions = QHBoxLayout()
        self.browse_btn = QPushButton("Browse Snapshot")
        self.browse_btn.setObjectName("dialogPrimary")
        self.browse_btn.setEnabled(False)
        self.browse_btn.clicked.connect(self._browse_snapshot)
        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("dialogSecondary")
        remove_btn.clicked.connect(self._remove_path)
        file_actions.addWidget(self.browse_btn)
        file_actions.addWidget(remove_btn)
        file_actions.addStretch(1)
        files_layout.addLayout(file_actions)
        self.selected_paths.toggled.connect(self.paths_list.setEnabled)
        self.selected_paths.toggled.connect(self.browse_btn.setEnabled)
        self.add_step("Files", files, self._validate_files)

        destination, destination_layout = _page(
            "Choose a destination",
            "Restore to a safe folder, or put files back in their original locations.",
        )
        self.to_original = QCheckBox(
            "Restore to original locations (may overwrite existing files)"
        )
        destination_layout.addWidget(self.to_original)
        target_row = QHBoxLayout()
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Select a restore destination")
        browse_target = QPushButton("Browse")
        browse_target.setObjectName("dialogSecondary")
        browse_target.clicked.connect(self._browse_target)
        target_row.addWidget(self.target_input, stretch=1)
        target_row.addWidget(browse_target)
        destination_layout.addLayout(target_row)
        destination_layout.addStretch(1)
        self.to_original.toggled.connect(self.target_input.setDisabled)
        self.to_original.toggled.connect(browse_target.setDisabled)
        self.add_step("Destination", destination, self._validate_destination)

        review, review_layout = _page(
            "Review restore",
            "Check these details carefully before starting the restore.",
        )
        self.review_label = QLabel()
        self.review_label.setObjectName("wizardReview")
        self.review_label.setWordWrap(True)
        self.review_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        review_layout.addWidget(self.review_label, stretch=1)
        self.add_step("Review", review)

    def _load_snapshots(self) -> None:
        repo_name = str(self.repo_combo.currentData() or "")
        self._snapshots = []
        self.snapshot_combo.clear()
        if not repo_name:
            self.snapshot_combo.addItem("Select a repository first", "")
            return
        self.snapshot_combo.addItem("Loading snapshots…", "")
        self.snapshot_combo.setEnabled(False)
        self.catalog_status.setText("Loading snapshot catalog…")
        self._catalog_request += 1
        request_id = self._catalog_request

        def _loaded(
            success,
            snapshots,
            error,
            requested_repo=repo_name,
            requested_id=request_id,
        ):
            if (
                requested_repo != str(self.repo_combo.currentData() or "")
                or requested_id != self._catalog_request
            ):
                return
            self.snapshot_combo.clear()
            self.snapshot_combo.setEnabled(True)
            if not success:
                self.snapshot_combo.addItem(error or "No snapshots available", "")
                self.catalog_status.setText(error or "No snapshots available")
                return
            self._snapshots = list(snapshots)
            for snapshot in reversed(self._snapshots):
                snap_id = snapshot.get(
                    "short_id", str(snapshot.get("id") or "")[:8]
                )
                stamp = str(snapshot.get("time") or "")
                try:
                    stamp = datetime.fromisoformat(
                        stamp.replace("Z", "+00:00")
                    ).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
                host_name = snapshot.get("hostname") or "Unknown host"
                self.snapshot_combo.addItem(
                    f"{snap_id} — {stamp} — {host_name}",
                    snapshot.get("id") or snap_id,
                )
            self.catalog_status.setText(
                f"{len(self._snapshots)} snapshot(s) available"
            )

        self.host.load_restore_snapshots(repo_name, _loaded)

    def _selected_snapshot(self) -> dict:
        snapshot_id = str(self.snapshot_combo.currentData() or "")
        return next(
            (
                snapshot
                for snapshot in self._snapshots
                if str(snapshot.get("id") or snapshot.get("short_id") or "")
                == snapshot_id
            ),
            {},
        )

    def _browse_snapshot(self) -> None:
        repo_name = str(self.repo_combo.currentData() or "")
        snapshot = self._selected_snapshot()
        snapshot_id = str(self.snapshot_combo.currentData() or "")
        repo, password = self.host.get_repository_by_name(repo_name)
        if not repo or not snapshot_id:
            self.error_label.setText("Select a repository and snapshot first.")
            return
        self.host._show_snapshot_browser_for_restore(
            snapshot_id,
            snapshot,
            repo,
            password,
            repo_name,
            on_paths_selected=self._set_selected_paths,
        )

    def _set_selected_paths(self, paths: list[str]) -> None:
        existing = {
            self.paths_list.item(i).text() for i in range(self.paths_list.count())
        }
        for path in paths:
            if path not in existing:
                self.paths_list.addItem(path)
                existing.add(path)
        self.selected_paths.setChecked(True)

    def _remove_path(self) -> None:
        row = self.paths_list.currentRow()
        if row >= 0:
            self.paths_list.takeItem(row)

    def _browse_target(self) -> None:
        target = QFileDialog.getExistingDirectory(
            self, "Select Restore Destination"
        )
        if target:
            self.target_input.setText(target)

    def _validate_source(self) -> str:
        if not self.repo_combo.currentData():
            return "Select a repository."
        if not self.snapshot_combo.currentData():
            return "Select an available snapshot."
        return ""

    def _validate_files(self) -> str:
        if self.selected_paths.isChecked() and not self.paths_list.count():
            return "Browse the snapshot and select at least one item."
        return ""

    def _validate_destination(self) -> str:
        if not self.to_original.isChecked() and not self.target_input.text().strip():
            return "Select a destination folder."
        return ""

    def on_step_changed(self, index: int) -> None:
        if index != 3:
            return
        request = self.restore_request()
        what = (
            "Entire snapshot"
            if not request["paths"]
            else "<br>".join(f"• {path}" for path in request["paths"])
        )
        destination = (
            "Original locations"
            if request["to_original"]
            else request["target"]
        )
        self.review_label.setText(
            f"<b>Repository</b><br>{request['repo_name']}<br><br>"
            f"<b>Snapshot</b><br>{request['snapshot_id'][:12]}<br><br>"
            f"<b>Files</b><br>{what}<br><br>"
            f"<b>Destination</b><br>{destination}"
        )

    def restore_request(self) -> dict:
        return {
            "repo_name": str(self.repo_combo.currentData() or ""),
            "snapshot_id": str(self.snapshot_combo.currentData() or ""),
            "paths": (
                [
                    self.paths_list.item(i).text()
                    for i in range(self.paths_list.count())
                ]
                if self.selected_paths.isChecked()
                else []
            ),
            "to_original": self.to_original.isChecked(),
            "target": self.target_input.text().strip(),
        }

