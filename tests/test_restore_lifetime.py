from contextlib import contextmanager
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event, Thread
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import restic_manager as desktop
from core.restore_destination import guard_destination


class RestoreLifetimeTests(unittest.TestCase):
    def exercise_close(self, *, timeout=0, cancelled=None, signal_error=False, wait_errors=False):
        events = []
        waiting = Event()
        allow_exit = Event()
        protected = Event()
        results = []
        folder = self.enterContext(tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent))
        target = Path(folder) / "destination"
        target.mkdir()
        with guard_destination(target) as (_, identity):
            pass

        @contextmanager
        def destination(*args):
            try:
                with guard_destination(*args):
                    events.append("protect")
                    protected.set()
                    yield
            finally:
                events.append("release")
                protected.clear()

        def launch(*_args, **_kwargs):
            events.append("launch")
            return child

        def kill():
            events.append("kill")
            if signal_error:
                raise OSError("simulated termination error")

        def wait(*, timeout):
            events.append("wait")
            if wait_errors and events.count("wait") == 1:
                raise OSError("simulated wait error")
            if events.count("wait") == (2 if wait_errors else 1):
                raise subprocess.TimeoutExpired("fixture", timeout)
            waiting.set()
            if not allow_exit.wait(5):
                raise subprocess.TimeoutExpired("fixture", timeout)
            events.append("exit confirmed")
            return 17

        child = SimpleNamespace(stdout=StringIO(), stderr=StringIO(),
                                kill=kill, terminate=lambda: events.append("terminate"),
                                poll=lambda: None, wait=wait)
        report = Mock()
        command = desktop.ResticCommand(sys.executable)

        def run():
            results.append(command.run_with_progress(
                ["restore"], timeout=timeout, progress_callback=report,
                restore_destination=(target, identity), restore_cancelled=cancelled,
            ))

        with (
            patch.object(desktop, "guard_destination", destination),
            patch.object(desktop.subprocess, "Popen", side_effect=launch),
            patch.object(desktop, "time", SimpleNamespace(
                monotonic=Mock(side_effect=[0, 2]), sleep=Mock(),
            )),
        ):
            worker = Thread(target=run, daemon=True)
            worker.start()
            try:
                self.assertTrue(waiting.wait(5), events)
                self.assertTrue(protected.is_set())
                self.assertEqual(results, [])
                self.assertIn("kill", events)
                self.assertNotIn("release", events)
                if os.name == "nt":
                    with self.assertRaises(OSError) as denied:
                        target.rename(target.with_name("moved"))
                    self.assertIn(denied.exception.winerror, (5, 32))
                report.assert_called_once_with(
                    "Restic exit is unconfirmed. The restore destination remains protected."
                )
            finally:
                allow_exit.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertFalse(protected.is_set())
        target.rename(target.with_name("moved"))
        self.assertEqual(events[:2], ["protect", "launch"])
        self.assertEqual(events[-2:], ["exit confirmed", "release"])
        self.assertFalse(results[0][0])
        self.assertIn("Restic exit code: 17", results[0][2])
        return results[0][2], events

    def test_timeout_keeps_guard_after_kill_and_until_exit(self):
        message, events = self.exercise_close(timeout=1)
        self.assertIn("time limit reached", message)
        self.assertEqual(events, ["protect", "launch", "kill", "wait", "wait", "exit confirmed", "release"])

    def test_cancellation_escalates_but_still_waits_for_exit(self):
        message, events = self.exercise_close(cancelled=lambda: True)
        self.assertIn("cancellation requested", message)
        self.assertEqual(events, ["protect", "launch", "terminate", "wait", "kill", "wait", "exit confirmed", "release"])

    def test_exception_after_launch_and_cleanup_errors_keep_guard_until_exit(self):
        def fail():
            raise ValueError("simulated execution error")

        message, events = self.exercise_close(cancelled=fail, signal_error=True, wait_errors=True)
        self.assertIn("Restore execution error (ValueError)", message)
        self.assertEqual(events, ["protect", "launch", "kill", "wait", "wait", "wait", "exit confirmed", "release"])

    def test_window_close_does_not_run_generic_thread_cleanup_during_restore(self):
        host = SimpleNamespace(_restore_operation_running=lambda: True, _cleanup_worker_threads=Mock())
        event = Mock()
        with patch.object(desktop, "show_framed_message") as message:
            desktop.ResticManagerWindow.closeEvent(host, event)
        event.ignore.assert_called_once()
        event.accept.assert_not_called()
        host._cleanup_worker_threads.assert_not_called()
        message.assert_called_once()

    def test_sidebar_exit_respects_window_close(self):
        host = SimpleNamespace(close=Mock())
        desktop.ResticManagerWindow.switch_page(host, -1)
        host.close.assert_called_once()
