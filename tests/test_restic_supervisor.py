import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Event
import time
import unittest
from unittest.mock import patch

from core.restic_supervisor import ExecutionRequest, ExecutionState, Outcome, StopPolicy, start


_GATED = (
    "import socket, sys; "
    "s = socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=20); "
    "print('started', flush=True); s.recv(1); s.close()"
)


class SupervisorTests(unittest.TestCase):
    def launch(self, code, *args, **options):
        execution = start(ExecutionRequest(sys.executable, ("-B", "-u", "-c", code, *args), **options))
        self.addCleanup(execution.wait, 25)
        return execution

    def gated(self, **options):
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(10)
        execution = self.launch(_GATED, str(listener.getsockname()[1]), **options)
        connection, _ = listener.accept()
        self.addCleanup(connection.close)
        return execution, connection

    def result(self, execution):
        result = execution.wait(10)
        self.assertIsNotNone(result)
        self.assertEqual(execution.state, ExecutionState.FINISHED)
        self.assertFalse(execution.process_is_running)
        self.assertFalse(execution.cancel())
        return result

    def test_exit_success_captures_both_streams_and_identity(self):
        execution = self.launch(
            "import sys; print('out'); print('err', file=sys.stderr)",
            profile_ref="test-profile", repository_ref="test-repo",
        )
        result = self.result(execution)
        self.assertEqual((result.outcome, result.exit_code), (Outcome.COMPLETED, 0))
        self.assertEqual((result.stdout.strip(), result.stderr.strip()), ("out", "err"))
        self.assertEqual((result.profile_ref, result.repository_ref), ("test-profile", "test-repo"))
        self.assertEqual(result.pid, execution.pid)
        self.assertIsNotNone(result.started_at)
        self.assertEqual({event.stream for event in execution.drain_progress()}, {"stdout", "stderr"})

    def test_nonzero_codes_are_preserved(self):
        for code in (1, 11, 73, 130):
            with self.subTest(code=code):
                result = self.result(self.launch(f"raise SystemExit({code})"))
                self.assertEqual(result.exit_code, code)
                self.assertFalse(result.succeeded)
                self.assertEqual(result.outcome, Outcome.INTERRUPTED if code == 130 else Outcome.FAILED)

    def test_active_and_cancel_pending_until_actual_exit(self):
        execution, connection = self.gated()
        self.assertTrue(execution.process_is_running)
        self.assertEqual(execution.state, ExecutionState.RUNNING)
        self.assertTrue(execution.cancel())
        self.assertFalse(execution.cancel())
        self.assertEqual(execution.state, ExecutionState.STOP_REQUESTED)
        self.assertIsNone(execution.wait(0))
        self.assertTrue(execution.process_is_running)
        connection.sendall(b"x")
        result = self.result(execution)
        self.assertEqual((result.outcome, result.exit_code), (Outcome.CANCELLED, 0))
        self.assertFalse(result.succeeded)

    def test_opt_in_termination_is_observed(self):
        execution, connection = self.gated(stop_policy=StopPolicy.TERMINATE_CHILD)
        self.assertTrue(execution.cancel())
        result = self.result(execution)
        self.assertEqual(result.outcome, Outcome.CANCELLED)
        self.assertNotEqual(result.exit_code, 0)
        connection.settimeout(5)
        try:
            self.assertEqual(connection.recv(1), b"")
        except ConnectionResetError:
            # Terminating the fixture may reset its socket instead of sending EOF.
            pass

    def test_timeout_is_distinct_from_cancellation(self):
        result = self.result(self.launch(
            "import threading; threading.Event().wait(20)", timeout=0.2,
            stop_policy=StopPolicy.TERMINATE_CHILD,
        ))
        self.assertEqual(result.outcome, Outcome.TIMED_OUT)
        self.assertNotEqual(result.exit_code, 0)
        self.assertFalse(result.succeeded)

    def test_timeout_can_remain_pending_while_child_runs(self):
        execution, connection = self.gated(timeout=0.5)
        until = time.monotonic() + 5
        poll = Event()
        while execution.stop_reason is None and time.monotonic() < until:
            poll.wait(0.01)
        self.assertEqual(execution.stop_reason, Outcome.TIMED_OUT)
        self.assertEqual(execution.state, ExecutionState.STOP_REQUESTED)
        self.assertIsNone(execution.wait(0))
        self.assertTrue(execution.process_is_running)
        connection.sendall(b"x")
        result = self.result(execution)
        self.assertEqual((result.outcome, result.exit_code), (Outcome.TIMED_OUT, 0))

    def test_argument_list_preserves_windows_special_characters(self):
        args = ("a b", "a&b", 'a"b', "x|y", "^%!*", "á space\\", "")
        result = self.result(self.launch(
            "import json, os, sys; print(json.dumps([sys.argv[1:], os.getcwd()]))",
            *args, cwd=Path("tests"),
        ))
        actual_args, cwd = json.loads(result.stdout)
        self.assertEqual(actual_args, list(args))
        self.assertEqual(Path(cwd), Path("tests").resolve())

    def test_missing_executable_and_startup_error(self):
        missing = self.result(start(ExecutionRequest(
            str(Path("tests/missing-restic.exe").resolve()), ("version",),
        )))
        self.assertEqual(missing.outcome, Outcome.START_FAILED)
        self.assertIsNone(missing.pid)
        self.assertIsNone(missing.exit_code)
        with patch("core.restic_supervisor.subprocess.Popen", side_effect=OSError(5, "private details")):
            failed = self.result(self.launch("print(1)"))
        self.assertEqual(failed.outcome, Outcome.START_FAILED)
        self.assertIn("5", failed.detail)
        self.assertNotIn("private details", failed.detail)

    def test_invalid_requests_do_not_launch_anything(self):
        with patch("core.restic_supervisor.subprocess.Popen") as popen:
            for request in (
                ExecutionRequest(sys.executable, ("bad\0arg",)),
                ExecutionRequest(sys.executable, ("version",), timeout=float("inf")),
                ExecutionRequest(sys.executable, ("https://user:example@localhost",)),
                ExecutionRequest(sys.executable, ("version",), environment={"BAD=KEY": "value"}),
            ):
                self.assertEqual(self.result(start(request)).outcome, Outcome.START_FAILED)
        popen.assert_not_called()

    def test_busy_pipes_are_drained_and_closed(self):
        children = []
        original_popen = subprocess.Popen

        def track(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            children.append(child)
            return child

        with patch("core.restic_supervisor.subprocess.Popen", side_effect=track) as popen:
            result = self.result(self.launch(
                "import os; "
                "[[os.write(fd, (b'x' * 4095) + b'\\n') for fd in (1, 2)] for _ in range(128)]"
            ))
        self.assertEqual(result.exit_code, 0)
        self.assertEqual((len(result.stdout.splitlines()), len(result.stderr.splitlines())), (128, 128))
        self.assertFalse(result.output_truncated)
        self.assertIs(popen.call_args.kwargs["shell"], False)
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(children[0].stdout.closed)
        self.assertTrue(children[0].stderr.closed)

    def test_tail_limit_and_final_summary(self):
        summary = json.dumps({"message_type": "summary", "total_files_processed": 1, "snapshot_id": "ab" * 32})
        result = self.result(self.launch(
            "import os, sys; [os.write(1, (b'x'*4095)+b'\\n') for _ in range(280)]; print(sys.argv[1])",
            summary, validate_backup=True,
        ))
        self.assertEqual(result.outcome, Outcome.COMPLETED)
        self.assertEqual(result.snapshot_id, "ab" * 32)
        self.assertTrue(result.output_truncated)
        self.assertLessEqual(len(result.stdout), 1024 * 1024)

    def test_backup_requires_documented_summary(self):
        base = {"message_type": "summary", "total_files_processed": 1}
        cases = [
            ({"message_type": "summary"}, 0, True, Outcome.FAILED),
            (base, 0, True, Outcome.UNCHANGED),
            (base, 0, False, Outcome.FAILED),
            ({**base, "dry_run": True}, 0, True, Outcome.FAILED),
            ({**base, "snapshot_id": "ab" * 32}, 3, True, Outcome.INCOMPLETE),
            ({**base, "snapshot_id": "ab" * 32}, 0, True, Outcome.COMPLETED),
        ]
        for summary, code, allow_skip, wanted in cases:
            with self.subTest(wanted=wanted):
                result = self.result(self.launch(
                    "import sys; print(sys.argv[1]); raise SystemExit(int(sys.argv[2]))",
                    json.dumps(summary), str(code), validate_backup=True, allow_unchanged=allow_skip,
                ))
                self.assertEqual(result.outcome, wanted)
                self.assertEqual(result.exit_code, code)

    def test_environment_and_credential_redaction(self):
        secret = "fictitious-secret"
        request = ExecutionRequest(sys.executable, (
            "-c", "import os, sys; print(os.environ['RESTIC_PASSWORD']); "
            "print(os.getenv('RESTIC_REPOSITORY')); "
            "print(os.environ['RESTIC_PASSWORD'], file=sys.stderr)",
        ), environment={"RESTIC_PASSWORD": secret})
        with patch.dict(os.environ, {"RESTIC_REPOSITORY": "personal-placeholder"}), patch(
            "core.restic_supervisor.subprocess.Popen", wraps=subprocess.Popen,
        ) as popen:
            execution = start(request)
            result = self.result(execution)
        self.assertTrue(result.succeeded)
        self.assertNotIn(secret, repr(request))
        self.assertNotIn(secret, str(popen.call_args.args[0]))
        self.assertEqual(result.stdout.splitlines(), ["[redacted]", "None"])
        self.assertEqual(result.stderr.strip(), "[redacted]")
        self.assertFalse(any(secret in event.line for event in execution.drain_progress()))

    def test_import_is_headless(self):
        code = (
            "import sys; import core.restic_supervisor; "
            "assert 'PySide6' not in sys.modules and 'restic_manager' not in sys.modules"
        )
        self.assertTrue(self.result(self.launch(code)).succeeded)
