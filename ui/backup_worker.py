"""Deliver supervised backup events to Qt without owning the Restic process."""

import json
import math

from PySide6.QtCore import QObject, QTimer, Signal

from core import restic_supervisor


class BackupWorker(QObject):
    completed = Signal(object)
    progress = Signal(str)
    progress_data = Signal(dict)
    stopping = Signal(object)

    def __init__(self, request: restic_supervisor.ExecutionRequest, parent=None):
        super().__init__(parent)
        self._request = request
        self._execution = None
        self._reported_stop = None
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._update)

    def start(self) -> None:
        self._execution = restic_supervisor.start(self._request)
        self._request = None
        self._timer.start()

    def cancel(self) -> bool:
        return self._execution is not None and self._execution.cancel()

    def isRunning(self) -> bool:
        # Keep the window open until the terminal result has been delivered to it.
        return self._timer.isActive()

    def _update(self) -> None:
        execution = self._execution
        result = execution.wait(0)
        stop = execution.stop_reason
        if stop is not None and stop is not self._reported_stop:
            self._reported_stop = stop
            self.stopping.emit(stop)
        for event in execution.drain_progress():
            self.progress.emit(event.line)
            if event.stream == "stdout" and stop is None:
                self._emit_status(event.line)
        if result is not None:
            self._timer.stop()
            self.completed.emit(result)

    def _emit_status(self, line: str) -> None:
        try:
            status = json.loads(line)
        except ValueError:
            return
        if not isinstance(status, dict) or status.get("message_type") != "status":
            return
        fraction = status.get("percent_done", 0)
        if not isinstance(fraction, (int, float)) or not 0 <= fraction <= 1 or not math.isfinite(fraction):
            return
        progress = {"percent": fraction * 100}
        for field in ("files_done", "total_files", "bytes_done", "total_bytes"):
            value = status.get(field, 0)
            if type(value) is int and value >= 0:
                progress[field] = value
        remaining = status.get("seconds_remaining", 0)
        if type(remaining) is int and remaining >= 0:
            progress["eta"] = remaining
        files = status.get("current_files")
        if isinstance(files, list):
            progress["current_files"] = [path for path in files if isinstance(path, str)]
        self.progress_data.emit(progress)
