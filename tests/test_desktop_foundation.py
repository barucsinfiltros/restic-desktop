import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import restic_supervisor


class DesktopFoundationTests(unittest.TestCase):
    def test_widgets_import_without_legacy_app_and_keep_public_exports(self):
        code = """
import sys
from PySide6.QtWidgets import QApplication
from ui import NavSidebar, SectionCard, StatCard
from ui import themes
from ui.charts import DonutChart, RoundedBarChart
from ui.framed_dialog import FramedDialog
from ui.wizard_dialog import WizardDialog
from ui.rounded_menu import RoundedMenu
from ui.hover_tip import ThemedHoverTip
from ui.icons import tinted_icon
assert 'restic_manager' not in sys.modules
assert 'core.restic_supervisor' not in sys.modules
assert 'ui.dashboard' not in sys.modules
app = QApplication([])
widgets = [NavSidebar(), SectionCard('test'), StatCard('test'), DonutChart(),
           RoundedBarChart(), FramedDialog('test'), WizardDialog(title='test'),
           RoundedMenu(), ThemedHoverTip()]
themes.apply_widget_theme(app, 'dark')
assert app.styleSheet()
assert not tinted_icon('snapshot.svg', '#000000').isNull()
from ui import create_dashboard_page, create_backup_jobs_page
assert callable(create_dashboard_page) and callable(create_backup_jobs_page)
assert 'restic_manager' not in sys.modules
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], capture_output=True, text=True,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_qt_adapter_emits_only_after_the_supervised_child_exits(self):
        code = """
import sys
from PySide6.QtCore import QCoreApplication, QTimer
from core.restic_supervisor import ExecutionRequest, Outcome
from ui.backup_worker import BackupWorker
app = QCoreApplication([])
request = ExecutionRequest(sys.executable, ('-c', 'import sys; print("fixture"); sys.exit(11)'))
worker = BackupWorker(request)
observed = []
worker.progress.connect(observed.append)
def completed(result):
    assert result.outcome is Outcome.FAILED and result.exit_code == 11
    assert observed == ['fixture'] and not worker.isRunning()
    app.exit(0)
worker.completed.connect(completed)
QTimer.singleShot(5000, lambda: app.exit(1))
worker.start()
sys.exit(app.exec())
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unregister_only_changes_registration(self):
        import restic_manager as desktop

        repository = {"name": "fixture", "path": "unused"}
        host = SimpleNamespace(
            settings_manager=Mock(), _framed_confirm=Mock(return_value=True),
            refresh_repository_list=Mock(), update_repository_combos=Mock(), log=Mock(),
        )
        host.settings_manager.get.return_value = [repository]
        with patch("shutil.rmtree") as delete, patch.object(desktop.rclone_util, "run_rclone") as rclone:
            desktop.ResticManagerWindow.delete_repository(host, 0)
        host.settings_manager.set.assert_called_once_with("repositories", [])
        delete.assert_not_called()
        rclone.assert_not_called()

    def test_original_restore_cannot_start_the_legacy_executor(self):
        import restic_manager as desktop

        host = SimpleNamespace(
            _restore_operation_running=lambda: False,
            _repository_status_blocks_foreground_operation=lambda _: False,
            _launch_restore_worker=Mock(),
        )
        with patch.object(desktop, "show_framed_message") as message:
            desktop.ResticManagerWindow._restore_paths_from_snapshot(
                host, [], snapshot_id="fixture", repo={}, password="",
                parent_dialog=None, to_original=True,
            )
        message.assert_called_once()
        host._launch_restore_worker.assert_not_called()

    def test_alternative_restore_rejects_nonempty_destination(self):
        import restic_manager as desktop

        host = SimpleNamespace(_repo_env=Mock())
        with patch.object(desktop, "show_framed_message") as message:
            worker = desktop.ResticManagerWindow._launch_restore_worker(
                host, repo={}, password="", snapshot_id="fixture",
                target=str(Path(__file__).resolve().parent),
            )
        self.assertIsNone(worker)
        message.assert_called_once()
        host._repo_env.assert_not_called()

    def test_cli_persists_exit_code_and_propagates_failure(self):
        import restic_manager as desktop

        settings = Mock()
        settings.get.side_effect = {
            "backup_jobs": [{"name": "fixture", "repositories": ["test"], "paths": ["unused"]}],
            "repositories": [{"name": "test"}],
            "restic_path": sys.executable,
        }.get
        settings.filename = "unused.json"
        with (
            patch.object(desktop, "ResticSettingsManager", return_value=settings),
            patch.object(desktop, "build_repo_env", return_value={}),
            patch.object(desktop, "build_backup_args", return_value=["-c", "raise SystemExit(11)"]),
            patch.object(desktop.history_db, "insert_job_run") as insert,
            patch.object(desktop.history_db, "log_job_run_outcome"),
            patch("builtins.print"),
        ):
            self.assertEqual(desktop.run_job_cli("fixture"), 11)
        self.assertEqual(insert.call_args.kwargs["exit_code"], 11)
        self.assertFalse(insert.call_args.kwargs["success"])
        settings.save_settings.assert_not_called()

    def test_backup_paths_follow_the_end_of_options(self):
        from restic_manager import build_backup_args

        paths = ["C:\\Work with spaces\\", "-source"]
        args = build_backup_args({"path": "fixture"}, {"name": "sample", "paths": paths})
        self.assertEqual(args[-3:], ["--", *paths])
        self.assertIn("--skip-if-unchanged", args[:-3])

    def test_cancelled_backup_is_recorded_without_success_or_next_target(self):
        import restic_manager as desktop

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        result = restic_supervisor.ExecutionResult(
            "test", 123, now, now, 1, restic_supervisor.Outcome.CANCELLED, 0,
        )
        host = SimpleNamespace(
            _backup_job_name="fixture", _backup_repo_name="test", _backup_all_succeeded=True,
            _backup_batch_active=True, _record_job_run=Mock(), _backup_status_label=Mock(),
            _backup_cancel_btn=Mock(), _backup_progress_bar=Mock(), _on_backup_output=Mock(),
            _backup_close_btn=Mock(), log=Mock(),
        )
        with patch.object(desktop, "show_notification"), patch.object(desktop, "QTimer") as timer:
            desktop.ResticManagerWindow._on_backup_completed(host, result)
        self.assertFalse(host._record_job_run.call_args.kwargs["success"])
        self.assertEqual(host._record_job_run.call_args.kwargs["exit_code"], 0)
        self.assertFalse(host._backup_batch_active)
        host._backup_progress_bar.setValue.assert_not_called()
        timer.singleShot.assert_not_called()
