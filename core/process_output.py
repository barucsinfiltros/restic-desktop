"""Read available subprocess pipe bytes without waiting for descendants to close them."""

import os
from typing import BinaryIO

if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _peek = ctypes.WinDLL("kernel32", use_last_error=True).PeekNamedPipe
    _peek.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        wintypes.LPDWORD, wintypes.LPDWORD, wintypes.LPDWORD,
    ]
    _peek.restype = wintypes.BOOL


def prepare_pipe(pipe: BinaryIO) -> None:
    if os.name != "nt":
        os.set_blocking(pipe.fileno(), False)


def read_available(pipe: BinaryIO, limit: int = 65536) -> bytes | None:
    """Return bytes, b'' on EOF, or None when there is no data yet."""
    fd = pipe.fileno()
    if os.name == "nt":
        available = wintypes.DWORD()
        if not _peek(msvcrt.get_osfhandle(fd), None, 0, None, ctypes.byref(available), None):
            error = ctypes.get_last_error()
            if error in (109, 232):  # broken pipe / pipe is closing
                return b""
            raise ctypes.WinError(error)
        if not available.value:
            return None
        limit = min(limit, available.value)
    try:
        return os.read(fd, limit)
    except BlockingIOError:
        return None
