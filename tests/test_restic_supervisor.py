import json
from collections import deque
from io import BytesIO
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import restic_supervisor as supervisor
from core.restic_supervisor import ExecutionRequest, ExecutionState, Outcome, StopPolicy, StopReason, start


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
        self.assertEqual((result.outcome, result.exit_code), (Outcome.COMPLETED, 0))
        self.assertEqual(result.stop_reason, StopReason.CANCELLED)
        self.assertTrue(result.succeeded)

    def test_opt_in_termination_is_observed(self):
        execution, connection = self.gated(stop_policy=StopPolicy.TERMINATE_CHILD)
        self.assertTrue(execution.cancel())
        result = self.result(execution)
        self.assertIn(result.outcome, (Outcome.FAILED, Outcome.INTERRUPTED))
        self.assertEqual(result.stop_reason, StopReason.CANCELLED)
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
        self.assertEqual(result.stop_reason, StopReason.TIMED_OUT)
        self.assertIn(result.outcome, (Outcome.FAILED, Outcome.INTERRUPTED))
        self.assertNotEqual(result.exit_code, 0)
        self.assertFalse(result.succeeded)

    def monitor_backup(self, code, *, cancel=False, timeout=False, exit_before_timeout=False):
        execution = supervisor.Execution()
        execution.pid = 123
        request = ExecutionRequest("fixture", ("backup",), validate_backup=True,
                                   timeout=1 if timeout else None)
        snapshot = "ab" * 32
        summary = json.dumps({
            "message_type": "summary", "snapshot_id": snapshot, "total_files_processed": 1,
        }).encode()
        child = SimpleNamespace(
            stdout=BytesIO(summary + b"\n"), stderr=BytesIO(),
            poll=Mock(side_effect=[None, code] if not timeout or exit_before_timeout else [None, None, code]),
        )
        if cancel:
            self.assertTrue(execution.cancel())
        inspected = False

        def read(pipe):
            nonlocal inspected
            if not inspected:
                inspected = True
                if exit_before_timeout:
                    self.assertFalse(execution.cancel())
                else:
                    self.assertEqual(execution.state, ExecutionState.STOP_REQUESTED)
                    self.assertIsNone(execution.wait(0))
                    self.assertTrue(execution.process_is_running)
            return pipe.read()

        progressed = []
        original_emit = execution._emit

        def emit(event):
            progressed.append(execution.process_is_running)
            original_emit(event)

        with (
            patch.object(supervisor.time, "monotonic", return_value=2),
            patch.object(supervisor, "read_available", side_effect=read),
            patch.object(supervisor, "prepare_pipe"),
            patch.object(execution, "_emit", side_effect=emit),
        ):
            supervisor._monitor(execution, request, child, 0, lambda value: value)
        result = self.result(execution)
        self.assertEqual(progressed, [not exit_before_timeout])
        self.assertEqual(result.exit_code, code)
        self.assertEqual(result.snapshot_id, snapshot)
        self.assertTrue(result.snapshot_created)
        self.assertEqual(result.stop_reason, None if exit_before_timeout else
                         StopReason.CANCELLED if cancel else StopReason.TIMED_OUT)
        supervisor._finish(execution, request, 0, Outcome.FAILED, 99)
        self.assertIs(execution.wait(0), result)
        return result

    def test_cancel_preserves_success_incomplete_and_failure(self):
        for code, expected in [(0, Outcome.COMPLETED), (3, Outcome.INCOMPLETE), (11, Outcome.FAILED)]:
            with self.subTest(code=code):
                result = self.monitor_backup(code, cancel=True)
                self.assertEqual(result.outcome, expected)
                self.assertTrue(result.stops_batch)

    def test_timeout_preserves_success_and_failure(self):
        for code, expected in [(0, Outcome.COMPLETED), (11, Outcome.FAILED)]:
            with self.subTest(code=code):
                result = self.monitor_backup(code, timeout=True)
                self.assertEqual(result.outcome, expected)
                self.assertTrue(result.stops_batch)

    def test_exit_before_timeout_check_does_not_register_a_timeout(self):
        result = self.monitor_backup(0, timeout=True, exit_before_timeout=True)
        self.assertEqual(result.outcome, Outcome.COMPLETED)
        self.assertFalse(result.stops_batch)

    def test_unconfirmed_exit_is_interrupted(self):
        request = ExecutionRequest("fixture", ("backup",), validate_backup=True)
        self.assertEqual(supervisor._classify(request, None, b"")[0], Outcome.INTERRUPTED)

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
            "import os, sys; [os.write(1, (b'x'*4095)+b'\\n') for _ in range(1100)]; print(sys.argv[1])",
            summary, validate_backup=True,
        ))
        self.assertEqual(result.outcome, Outcome.COMPLETED)
        self.assertEqual(result.snapshot_id, "ab" * 32)
        self.assertTrue(result.output_truncated)
        self.assertLessEqual(len(result.stdout), 1024 * 1024)

    def monitor_post_exit_output(self, stdout_chunks, stderr_chunks=(b"final diagnostic\n",)):
        execution = supervisor.Execution()
        execution.pid = 123
        request = ExecutionRequest("fixture", ("backup",), validate_backup=True)
        child = SimpleNamespace(stdout=BytesIO(), stderr=BytesIO(), poll=Mock(return_value=0))
        pending = {
            child.stdout: deque(stdout_chunks),
            child.stderr: deque(stderr_chunks),
        }

        def read(pipe):
            child.poll.assert_called_once_with()
            self.assertFalse(execution.process_is_running)
            self.assertIsNone(execution.wait(0))
            chunks = pending[pipe]
            # No bytes available is distinct from EOF on an inherited pipe.
            chunk = chunks.popleft() if chunks else None
            if isinstance(chunk, OSError):
                raise chunk
            return chunk

        with (
            patch.object(supervisor, "prepare_pipe"),
            patch.object(supervisor, "read_available", side_effect=read),
        ):
            supervisor._monitor(execution, request, child, 0, lambda text: text)

        self.assertTrue(child.stdout.closed)
        self.assertTrue(child.stderr.closed)
        result = self.result(execution)
        self.assertEqual(result.exit_code, 0)
        return result, list(pending[child.stdout])

    def test_post_exit_drain_recovers_final_summary(self):
        snapshot = "ab" * 32
        summary = json.dumps({
            "message_type": "summary", "total_files_processed": 1, "snapshot_id": snapshot,
        }) + "\n"
        data = summary.encode()
        result, unread = self.monitor_post_exit_output([b"progress\n", data[:50], data[50:]])
        self.assertEqual(unread, [])
        self.assertEqual(result.stdout, "progress\n" + summary)
        self.assertEqual(result.stderr, "final diagnostic\n")
        self.assertEqual(result.outcome, Outcome.COMPLETED)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.snapshot_id, snapshot)
        self.assertFalse(result.output_truncated)

    def test_post_exit_drain_limit_rejects_backup_without_summary(self):
        summary = json.dumps({
            "message_type": "summary", "total_files_processed": 1, "snapshot_id": "ab" * 32,
        }).encode() + b"\n"
        # Short records isolate the 64-pass budget from byte and line limits.
        pending = [b"progress\n"] * 64 + [summary]
        result, unread = self.monitor_post_exit_output(pending)
        self.assertEqual(unread, [summary])
        self.assertEqual(result.stdout, "progress\n" * 64)
        self.assertEqual(result.outcome, Outcome.FAILED)
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.snapshot_id)
        self.assertTrue(result.output_truncated)
        self.assertIn("No valid final Restic backup summary", result.detail)
        self.assertIn("Subprocess output capture was incomplete", result.detail)

    def backup_summary(self, snapshot="ab" * 32):
        return json.dumps({
            "message_type": "summary", "total_files_processed": 1, "snapshot_id": snapshot,
        }).encode() + b"\n"

    def assert_unconfirmed_stdout(self, result):
        self.assertEqual(result.outcome, Outcome.FAILED)
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.snapshot_id)
        self.assertTrue(result.output_truncated)
        self.assertIn("Subprocess output capture was incomplete (stdout)", result.detail)

    def test_post_exit_stdout_loss_invalidates_previously_read_summary(self):
        summary = self.backup_summary()
        for ending in ([OSError("stdout read failed")], [b"\n"] * 64):
            with self.subTest(ending=type(ending[0]).__name__):
                result, _ = self.monitor_post_exit_output([summary, *ending])
                self.assertIn(summary.decode(), result.stdout)
                self.assert_unconfirmed_stdout(result)

    def test_post_exit_stderr_loss_preserves_complete_stdout_summary(self):
        for eof, diagnostic in (
            ([b""], [b"error\n", OSError("stderr read failed")]),
            ([], [b"error\n"] * 65),
        ):
            with self.subTest(stdout_eof=bool(eof), stderr_reads=len(diagnostic)):
                result, _ = self.monitor_post_exit_output([self.backup_summary(), *eof], diagnostic)
                self.assertEqual(result.outcome, Outcome.COMPLETED)
                self.assertTrue(result.succeeded)
                self.assertEqual(result.snapshot_id, "ab" * 32)
                self.assertTrue(result.output_truncated)
                self.assertIn("Subprocess output capture was incomplete (stderr)", result.detail)

    def test_post_exit_partial_stdout_record_at_eof_invalidates_summary(self):
        result, _ = self.monitor_post_exit_output([
            self.backup_summary(), b'{"message_type": "status"', b"",
        ])
        self.assert_unconfirmed_stdout(result)

    def test_post_exit_oversized_partial_stdout_record_invalidates_summary(self):
        fragment = b"x" * (supervisor._MAX_LINE // 2 + 1)
        result, _ = self.monitor_post_exit_output([
            self.backup_summary(), fragment, fragment, b"",
        ])
        self.assert_unconfirmed_stdout(result)

    def test_post_exit_summary_after_discarded_record_remains_valid(self):
        fragment = b"x" * (supervisor._MAX_LINE // 2 + 1)
        result, _ = self.monitor_post_exit_output([fragment, fragment, b"\n", self.backup_summary(), b""])
        self.assertEqual(result.outcome, Outcome.COMPLETED)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.snapshot_id, "ab" * 32)
        self.assertTrue(result.output_truncated)
        self.assertEqual(result.detail, "")

    def test_post_exit_unterminated_json_cannot_replace_summary(self):
        result, _ = self.monitor_post_exit_output([
            self.backup_summary(), self.backup_summary("cd" * 32).rstrip(b"\n"), b"",
        ])
        self.assert_unconfirmed_stdout(result)

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
                expected_created = False if wanted is Outcome.UNCHANGED else (
                    True if wanted in (Outcome.COMPLETED, Outcome.INCOMPLETE) else None
                )
                self.assertIs(result.snapshot_created, expected_created)

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
