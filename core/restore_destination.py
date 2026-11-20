"""Validate empty restore destinations and pin Windows directory names."""

from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import stat


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class _FileInfo(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD),
            ("created", wintypes.FILETIME),
            ("accessed", wintypes.FILETIME),
            ("written", wintypes.FILETIME),
            ("volume", wintypes.DWORD),
            ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD),
            ("links", wintypes.DWORD),
            ("index_high", wintypes.DWORD),
            ("index_low", wintypes.DWORD),
        ]

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _open = _kernel.CreateFileW
    _open.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    _open.restype = wintypes.HANDLE
    _info = _kernel.GetFileInformationByHandle
    _info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FileInfo)]
    _info.restype = wintypes.BOOL
    _close = _kernel.CloseHandle
    _close.argtypes = [wintypes.HANDLE]
    _close.restype = wintypes.BOOL
    _drive_type = _kernel.GetDriveTypeW
    _drive_type.argtypes = [wintypes.LPCWSTR]
    _drive_type.restype = wintypes.UINT

    def _open_component(path, stack):
        # Attribute-only access does not participate in Windows share checks.
        list_directory_and_read_attributes = 0x01 | 0x80
        share_read_write = 0x3  # Deliberately omit FILE_SHARE_DELETE.
        open_existing = 3
        directory_no_follow = 0x02000000 | 0x00200000
        handle = _open(str(path), list_directory_and_read_attributes, share_read_write, None,
                       open_existing, directory_no_follow, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        stack.callback(_close, handle)
        return handle

    def _directory_identity(handle):
        info = _FileInfo()
        if not _info(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if (info.attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
                or not info.attributes & stat.FILE_ATTRIBUTE_DIRECTORY):
            raise ValueError("A restore path component is not an ordinary directory.")
        return info.volume, info.index_high, info.index_low


def _destination_path(target):
    path = Path(target)
    if "\0" in str(path) or not path.is_absolute() or len(path.parts) < 2 or ".." in path.parts:
        raise ValueError("Choose an absolute restore directory below a filesystem root.")
    if os.name == "nt":
        if (len(path.drive) != 2 or not path.drive[0].isascii()
                or not path.drive[0].isalpha() or path.drive[1] != ":"
                or any(os.path.isreserved(part) for part in path.parts[1:])
                or _drive_type(path.anchor) not in (2, 3)):
            raise ValueError("Choose an ordinary directory on a local Windows drive.")
    return path


def _posix_identity(component):
    info = component.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("A restore path component is not an ordinary directory.")
    return info.st_dev, info.st_ino


@contextmanager
def guard_destination(target, expected=None):
    """Check identities and emptiness, holding Windows handles until context exit."""
    path = _destination_path(target)
    components = (*reversed(path.parents), path)
    with ExitStack() as stack:
        if os.name == "nt":
            handles = []
            identities = []
            for component in components:
                handle = _open_component(component, stack)
                identities.append(_directory_identity(handle))
                handles.append(handle)
            identity_chain = tuple(identities)
        else:
            identity_chain = tuple(_posix_identity(part) for part in components)
        if expected is not None and identity_chain != expected:
            raise ValueError("The restore path changed after validation.")
        with os.scandir(path) as entries:
            if next(entries, None) is not None:
                raise ValueError("The restore destination is no longer empty.")
        if os.name == "nt":
            current = tuple(
                _directory_identity(_open_component(part, stack)) for part in components
            )
            if any(_directory_identity(handle) != identity for handle, identity in zip(handles, identity_chain)):
                raise ValueError("The restore path changed during validation.")
        else:
            current = tuple(_posix_identity(part) for part in components)
        if current != identity_chain:
            raise ValueError("The restore path changed during validation.")
        yield path, identity_chain
