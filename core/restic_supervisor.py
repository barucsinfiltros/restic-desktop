"""Qt-independent execution of trusted Restic commands and their process lifecycle."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from threading import Event, Lock, Thread
import time
from typing import Mapping
from uuid import uuid4

from core.process_output import prepare_pipe, read_available


class ExecutionState(str, Enum):
    RUNNING = "running"
    STOP_REQUESTED = "stop_requested"
    FINISHED = "finished"


class Outcome(str, Enum):
    COMPLETED = "completed"
    UNCHANGED = "unchanged"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    INTERRUPTED = "interrupted"
    START_FAILED = "start_failed"


class StopReason(str, Enum):
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def message(self) -> str:
        return "Time limit reached" if self is StopReason.TIMED_OUT else "Stop requested"


class StopPolicy(str, Enum):
    WAIT = "wait"
    TERMINATE_CHILD = "terminate_child"


@dataclass(frozen=True)
class ExecutionRequest:
    executable: str
    arguments: tuple[str, ...] = field(repr=False)
    cwd: Path | None = None
    environment: Mapping[str, str] = field(default_factory=dict, repr=False)
    timeout: float | None = None
    # Hard termination is opt-in for processes whose caller can safely stop them.
    stop_policy: StopPolicy = StopPolicy.WAIT
    validate_backup: bool = False
    allow_unchanged: bool = False
    profile_ref: str | None = None
    repository_ref: str | None = None


@dataclass(frozen=True)
class Progress:
    stream: str
    line: str = field(repr=False)


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    pid: int | None
    started_at: datetime | None
    finished_at: datetime
    duration_seconds: float
    outcome: Outcome
    exit_code: int | None
    profile_ref: str | None = None
    repository_ref: str | None = None
    snapshot_id: str | None = None
    stdout: str = field(default="", repr=False)
    stderr: str = field(default="", repr=False)
    detail: str = ""
    output_truncated: bool = False
    stop_reason: StopReason | None = None

    @property
    def succeeded(self) -> bool:
        return self.outcome in (Outcome.COMPLETED, Outcome.UNCHANGED)

    @property
    def snapshot_created(self) -> bool | None:
        if self.snapshot_id is not None:
            return True
        return False if self.outcome is Outcome.UNCHANGED else None

    @property
    def stops_batch(self) -> bool:
        return self.stop_reason is not None or self.outcome is Outcome.INTERRUPTED


class Execution:
    """Handle for one process. Cancellation records intent until exit is observed."""

    def __init__(self) -> None:
        self.execution_id = uuid4().hex
        self.pid: int | None = None
        self.started_at: datetime | None = None
        self._lock = Lock()
        self._wake = Event()
        self._done = Event()
        self._exited = Event()
        self._result: ExecutionResult | None = None
        self._stop_reason: StopReason | None = None
        self._progress: deque[Progress] = deque(maxlen=256)

    @property
    def state(self) -> ExecutionState:
        with self._lock:
            if self._result is not None:
                return ExecutionState.FINISHED
            if self._stop_reason is not None:
                return ExecutionState.STOP_REQUESTED
            return ExecutionState.RUNNING

    @property
    def stop_reason(self) -> StopReason | None:
        with self._lock:
            return self._stop_reason

    def is_running(self) -> bool:
        """Whether the execution is still supervised, including exit finalization."""
        return self.state is not ExecutionState.FINISHED

    @property
    def process_is_running(self) -> bool:
        """Whether a launched process has yet to be observed exiting."""
        return self.pid is not None and not self._exited.is_set()

    def cancel(self) -> bool:
        return self._request_stop(StopReason.CANCELLED)

    def wait(self, timeout: float | None = None) -> ExecutionResult | None:
        return self._result if self._done.wait(timeout) else None

    def drain_progress(self) -> list[Progress]:
        with self._lock:
            events = list(self._progress)
            self._progress.clear()
            return events

    def _request_stop(self, reason: StopReason) -> bool:
        with self._lock:
            if self._result is not None or self._stop_reason is not None or self._exited.is_set():
                return False
            self._stop_reason = reason
            self._wake.set()
            return True

    def _emit(self, progress: Progress) -> None:
        with self._lock:
            self._progress.append(progress)


_MAX_CAPTURE = 1024 * 1024  # per stream, before redaction
_MAX_LINE = 65536
_AUTH_URL = re.compile(r"://[^:/\s@]*:[^/\s@]*@")
_SNAPSHOT_ID = re.compile(r"(?:[0-9a-f]{8}|[0-9a-f]{64})")


class _InvalidRequest(ValueError):
    """Validation message written by this module, with no request data."""


def _redactor(environment: Mapping[str, str]):
    values = set()
    for key, value in environment.items():
        if value and any(word in key.upper() for word in ("PASSWORD", "SECRET", "TOKEN", "ACCESS_KEY", "ACCOUNT_KEY")):
            values.add(value)
            values.update(part for part in value.splitlines() if part)
            for ascii_only in (True, False):
                values.add(json.dumps(value, ensure_ascii=ascii_only)[1:-1])
    pattern = re.compile("|".join(re.escape(v) for v in sorted(values, key=len, reverse=True))) if values else None

    def redact(text: str) -> str:
        text = _AUTH_URL.sub("://[redacted]@", text)
        return pattern.sub("[redacted]", text) if pattern else text

    return redact


class _Capture:
    def __init__(self, stream: str, pipe, emit, redact):
        self.stream = stream
        self.pipe = pipe
        self.emit = emit
        self.redact = redact
        self.tail = bytearray()
        self.pending = b""
        self.last_record = b""
        self.discard_line = False
        self.truncated = False
        self.incomplete = False
        self.closed = False

    def drain(self) -> bool:
        if self.closed:
            return False
        chunk = read_available(self.pipe)
        if chunk is None:
            return False
        if not chunk:
            self.close()
            return False
        self.tail.extend(chunk)
        if len(self.tail) > _MAX_CAPTURE:
            # Drop the first partial record as it may contain a fragment of a secret.
            boundary = self.tail.find(b"\n", len(self.tail) - _MAX_CAPTURE)
            if boundary < 0:
                self.tail.clear()
            else:
                del self.tail[:boundary + 1]
            self.truncated = True
        *lines, self.pending = (self.pending + chunk).split(b"\n")
        for line in lines:
            self._line(line)
            self.discard_line = False
        if len(self.pending) > _MAX_LINE:
            self.pending = b""
            self.last_record = b""
            self.discard_line = self.truncated = True
        return True

    def close(self) -> None:
        if not self.closed:
            if self.discard_line or self.pending.strip():
                self.incomplete = True
            if self.pending:
                self._line(self.pending)
            self.closed = True
            self.pipe.close()

    def _line(self, line: bytes) -> None:
        if self.discard_line or len(line) > _MAX_LINE:
            self.last_record = b""
            self.truncated = True
        elif line.strip():
            self.last_record = line
            self.emit(Progress(self.stream, self.redact(line.decode("utf-8", "replace").rstrip("\r"))))

    def output(self) -> str:
        # If data was truncated, omit an incomplete last line as well.
        tail = self.tail
        if self.truncated and not tail.endswith(b"\n"):
            tail = tail[:tail.rfind(b"\n") + 1]
        return self.redact(tail.decode("utf-8", "replace"))


def _prepare(request: ExecutionRequest) -> tuple[list[str], dict[str, str], Path]:
    if not isinstance(request.executable, str) or not request.executable or not isinstance(request.arguments, tuple) or not request.arguments:
        raise _InvalidRequest("An executable and an argument tuple are required.")
    if not all(isinstance(arg, str) and "\x00" not in arg for arg in request.arguments):
        raise _InvalidRequest("Arguments must be strings without NUL characters.")
    if request.timeout is not None and (not math.isfinite(request.timeout) or request.timeout <= 0):
        raise _InvalidRequest("The timeout must be a positive finite number.")
    if "\x00" in request.executable:
        raise _InvalidRequest("The executable contains an invalid character.")
    if not isinstance(request.stop_policy, StopPolicy):
        raise _InvalidRequest("Unknown stop policy.")
    if any(_AUTH_URL.search(arg) for arg in request.arguments):
        raise _InvalidRequest("Use the child environment for credentials instead of URL userinfo.")
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith("RESTIC_")}
    for key, value in request.environment.items():
        if not isinstance(key, str) or not isinstance(value, str) or not key or "=" in key or "\x00" in key + value:
            raise _InvalidRequest("The child environment contains an invalid entry.")
        if _AUTH_URL.search(value) and key.upper() in ("RESTIC_REPOSITORY", "RESTIC_FROM_REPOSITORY"):
            raise _InvalidRequest("Use separate credentials for repository URLs.")
        environment[key.upper() if os.name == "nt" else key] = value
    cwd = (request.cwd or Path.cwd()).resolve()
    if not cwd.is_dir():
        raise _InvalidRequest("The working directory must be an existing directory.")
    exe = Path(request.executable)
    if exe.is_absolute() or exe.name != request.executable:
        candidates = [cwd / exe]
    else:
        candidates = [cwd / folder / exe for folder in environment.get("PATH", os.defpath).split(os.pathsep) if folder]
    for candidate in candidates:
        found = shutil.which(str(candidate))
        if found and (os.name != "nt" or Path(found).suffix.lower() == ".exe"):
            return [found, *request.arguments], environment, cwd
    raise _InvalidRequest("The configured executable could not be resolved.")


def _classify(request: ExecutionRequest, code: int | None, final_stdout: bytes) -> tuple[Outcome, str | None, str]:
    summary = None
    if request.validate_backup:
        try:
            summary = json.loads(final_stdout)
        except (ValueError, UnicodeDecodeError):
            pass
    has_summary = (
        isinstance(summary, dict)
        and summary.get("message_type") == "summary"
        and summary.get("dry_run", False) is False
        and type(summary.get("total_files_processed")) is int
        and summary["total_files_processed"] >= 0
    )
    snapshot = summary.get("snapshot_id") if has_summary else None
    if not isinstance(snapshot, str) or not _SNAPSHOT_ID.fullmatch(snapshot):
        snapshot = None
    if code is None:
        return Outcome.INTERRUPTED, snapshot, "Process exit code could not be confirmed."
    if code == 130 or code < 0 or code == 0xC000013A:
        return Outcome.INTERRUPTED, snapshot, "Process was interrupted."
    if request.validate_backup and code == 3:
        return Outcome.INCOMPLETE, snapshot, "Some source data could not be read."
    if code != 0:
        return Outcome.FAILED, snapshot, "Process returned a non-zero exit code."
    if not request.validate_backup:
        return Outcome.COMPLETED, None, ""
    if snapshot is not None:
        return Outcome.COMPLETED, snapshot, ""
    if has_summary and "snapshot_id" not in summary and request.allow_unchanged:
        return Outcome.UNCHANGED, None, ""
    return Outcome.FAILED, None, "No valid final Restic backup summary was received."


def _finish(
    handle: Execution, request: ExecutionRequest, launched_at: float,
    outcome: Outcome, code: int | None = None, **details,
) -> None:
    with handle._lock:
        if handle._result is not None:
            return
        handle._result = ExecutionResult(
            handle.execution_id, handle.pid, handle.started_at, datetime.now(timezone.utc),
            time.monotonic() - launched_at, outcome, code,
            request.profile_ref, request.repository_ref, stop_reason=handle._stop_reason, **details,
        )
        handle._done.set()


def _monitor(handle: Execution, request: ExecutionRequest, process, launched_at: float, redact) -> None:
    captures = [
        _Capture("stdout", process.stdout, handle._emit, redact),
        _Capture("stderr", process.stderr, handle._emit, redact),
    ]
    deadline = None if request.timeout is None else launched_at + request.timeout
    termination_attempted = False
    termination_failed = False
    for stream in captures:
        try:
            prepare_pipe(stream.pipe)
        except OSError:
            stream.incomplete = True
            stream.close()

    def drain() -> list[_Capture]:
        received = []
        for stream in captures:
            try:
                if stream.drain():
                    received.append(stream)
            except OSError:
                stream.incomplete = True
                stream.close()
        return received

    while True:
        with handle._lock:
            code = process.poll()
            if code is not None:
                handle._exited.set()
                break
        if deadline is not None and time.monotonic() >= deadline:
            # Output processing may have taken long enough for the child to exit.
            with handle._lock:
                code = process.poll()
                if code is not None:
                    handle._exited.set()
                    break
                if handle._stop_reason is None:
                    handle._stop_reason = StopReason.TIMED_OUT
        if handle.stop_reason is not None and not termination_attempted and request.stop_policy is StopPolicy.TERMINATE_CHILD:
            termination_attempted = True
            try:
                process.terminate()
            except OSError:
                termination_failed = True
        if not drain():
            handle._wake.wait(0.02)
            handle._wake.clear()

    # Drain currently available bytes. A descendant keeping a pipe open cannot
    # postpone completion of the direct child or force an unbounded final drain.
    for _ in range(64):
        received = drain()
        if not received:
            break
    else:
        # Only streams still delivering bytes at the limit have unread output
        # that we cannot rule out. A busy stderr does not invalidate stdout.
        for stream in received:
            stream.incomplete = True
    for stream in captures:
        stream.close()
    stdout, stderr = captures
    final_stdout = b"" if stdout.incomplete else stdout.last_record
    outcome, snapshot, detail = _classify(request, code, final_stdout)
    incomplete = ", ".join(stream.stream for stream in captures if stream.incomplete)
    if incomplete:
        detail = f"{detail} Subprocess output capture was incomplete ({incomplete}).".strip()
    if termination_failed:
        detail = f"{detail} The termination call failed or the process had already exited.".strip()
    _finish(
        handle, request, launched_at, outcome, code, snapshot_id=snapshot,
        stdout=stdout.output(), stderr=stderr.output(), detail=detail,
        output_truncated=bool(incomplete) or stdout.truncated or stderr.truncated,
    )


def start(request: ExecutionRequest) -> Execution:
    """Start one execution. Startup errors produce a completed START_FAILED handle."""
    handle = Execution()
    launched_at = time.monotonic()
    try:
        command, environment, cwd = _prepare(request)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        detail = str(exc) if isinstance(exc, _InvalidRequest) else ""
        _finish(handle, request, launched_at, Outcome.START_FAILED, detail=detail or "Invalid execution request.")
        return handle
    redact = _redactor(environment)
    try:
        process = subprocess.Popen(
            command, cwd=cwd, env=environment, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, ValueError) as exc:
        error_code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
        _finish(handle, request, launched_at, Outcome.START_FAILED, detail=f"Could not start process (OS error {error_code}).")
        return handle
    handle.pid = process.pid
    handle.started_at = datetime.now(timezone.utc)
    monitor_args = (handle, request, process, time.monotonic(), redact)
    monitor = Thread(target=_monitor, args=monitor_args, name=f"restic-{process.pid}")
    try:
        monitor.start()
    except RuntimeError:
        _monitor(*monitor_args)  # Maintain ownership even if the thread cannot start.
    return handle
