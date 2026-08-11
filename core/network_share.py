"""Windows SMB network-share mount helpers for connect-only repositories."""

from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from typing import Dict, Iterator, Optional, Tuple


def is_network_repo(repo: Optional[dict]) -> bool:
    if not repo:
        return False
    return (repo.get("type") or "").lower() == "network"


def connect_only_enabled(repo: Optional[dict]) -> bool:
    if not is_network_repo(repo):
        return False
    return bool(repo.get("network_connect_only"))


def unc_share_root(server: str, share: str) -> str:
    server = (server or "").strip().strip("\\/")
    share = (share or "").strip().strip("\\/")
    if not server or not share:
        return ""
    return f"\\\\{server}\\{share}"


def build_unc_path(server: str, share: str, subpath: str = "") -> str:
    root = unc_share_root(server, share)
    if not root:
        return ""
    sub = (subpath or "").strip().replace("/", "\\").strip("\\")
    return f"{root}\\{sub}" if sub else root


def normalize_drive_letter(letter: str) -> str:
    raw = (letter or "").strip().upper().rstrip(":\\/")
    if len(raw) == 1 and raw.isalpha():
        return f"{raw}:"
    return ""


def effective_repo_path(repo: dict, *, mounted_drive: str = "") -> str:
    sub = (repo.get("network_subpath") or "").strip().replace("/", "\\").strip("\\")
    drive = normalize_drive_letter(mounted_drive or repo.get("network_drive") or "")
    if drive:
        return f"{drive}\\{sub}" if sub else f"{drive}\\"
    return (
        repo.get("path")
        or build_unc_path(
            repo.get("network_server") or "",
            repo.get("network_share") or "",
            repo.get("network_subpath") or "",
        )
    )


def _run_net_use(args: list, *, timeout: int = 60) -> Tuple[bool, str]:
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            ["net", "use", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creationflags,
        )
        out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return proc.returncode == 0, out
    except FileNotFoundError:
        return False, "net use command not found (Windows only)."
    except subprocess.TimeoutExpired:
        return False, "net use timed out."
    except Exception as exc:
        return False, str(exc)


def mount_share(
    repo: dict,
    *,
    username: str = "",
    password: str = "",
) -> Tuple[bool, str, str]:
    if os.name != "nt":
        return False, "Connect-only network shares are currently Windows-only.", ""

    server = (repo.get("network_server") or "").strip()
    share = (repo.get("network_share") or "").strip()
    root = unc_share_root(server, share)
    if not root:
        return False, "Network server and share are required.", ""

    drive = normalize_drive_letter(repo.get("network_drive") or "")
    user = (username or repo.get("network_user") or "").strip()
    pwd = password or ""

    if drive:
        _run_net_use([drive, "/delete", "/y"])
    else:
        _run_net_use([root, "/delete", "/y"])

    args = [drive, root] if drive else [root]
    if user:
        args.extend([f"/user:{user}", pwd])
    elif pwd:
        args.append(pwd)

    ok, out = _run_net_use(args)
    if not ok:
        probe = effective_repo_path(repo, mounted_drive=drive)
        parent = os.path.dirname(probe.rstrip("\\")) or probe
        if os.path.isdir(root) or os.path.isdir(parent) or os.path.isdir(probe):
            return True, "Share already accessible.", drive
        return False, out or "Failed to connect to network share.", ""
    return True, out or "Connected.", drive


def unmount_share(repo: dict, *, mounted_drive: str = "") -> Tuple[bool, str]:
    if os.name != "nt":
        return True, "Skipped (not Windows)."
    drive = normalize_drive_letter(mounted_drive or repo.get("network_drive") or "")
    root = unc_share_root(
        repo.get("network_server") or "",
        repo.get("network_share") or "",
    )
    target = drive if drive else root
    if not target:
        return True, "Nothing to disconnect."
    ok, out = _run_net_use([target, "/delete", "/y"])
    low = (out or "").lower()
    if not ok and ("not found" in low or "network connection could not be found" in low):
        return True, out
    return ok, out or ("Disconnected." if ok else "Failed to disconnect.")


@contextmanager
def network_share_session(
    repo: dict,
    *,
    username: str = "",
    password: str = "",
    force: bool = False,
) -> Iterator[Dict]:
    working = dict(repo or {})
    should = force or connect_only_enabled(working)
    mounted_drive = ""
    if not should:
        working["path"] = effective_repo_path(working)
        yield working
        return

    ok, msg, mounted_drive = mount_share(
        working, username=username, password=password
    )
    if not ok:
        raise RuntimeError(msg or "Could not connect to network share.")
    try:
        working["path"] = effective_repo_path(working, mounted_drive=mounted_drive)
        working["_network_mounted_drive"] = mounted_drive
        yield working
    finally:
        unmount_share(working, mounted_drive=mounted_drive)


def powershell_mount_block(repo: dict, *, password_ps_var: str = "$netPassword") -> str:
    if not connect_only_enabled(repo):
        return "# (network share always connected)"
    server = (repo.get("network_server") or "").strip()
    share = (repo.get("network_share") or "").strip()
    root = unc_share_root(server, share).replace('"', '`"')
    drive = normalize_drive_letter(repo.get("network_drive") or "")
    user = (repo.get("network_user") or "").strip().replace('"', '`"').replace("$", "`$")
    lines = [
        "# Connect network share for this backup only",
        f'$shareRoot = "{root}"',
        f'$netUser = "{user}"',
    ]
    if drive:
        lines.append(f'$shareDrive = "{drive}"')
        lines.append("net use $shareDrive /delete /y 2>$null | Out-Null")
        if user:
            lines.append(
                f"net use $shareDrive $shareRoot /user:$netUser {password_ps_var} | Out-Null"
            )
        else:
            lines.append("net use $shareDrive $shareRoot | Out-Null")
    else:
        lines.append("net use $shareRoot /delete /y 2>$null | Out-Null")
        if user:
            lines.append(
                f"net use $shareRoot /user:$netUser {password_ps_var} | Out-Null"
            )
        else:
            lines.append("net use $shareRoot | Out-Null")
    lines.append("if ($LASTEXITCODE -ne 0) {")
    lines.append('  Write-Host "Failed to connect network share: $shareRoot"')
    lines.append("  exit 1")
    lines.append("}")
    return "\n".join(lines)


def powershell_unmount_block(repo: dict) -> str:
    if not connect_only_enabled(repo):
        return "# (no network disconnect)"
    server = (repo.get("network_server") or "").strip()
    share = (repo.get("network_share") or "").strip()
    root = unc_share_root(server, share).replace('"', '`"')
    drive = normalize_drive_letter(repo.get("network_drive") or "")
    target = drive if drive else root
    return (
        f'net use "{target}" /delete /y 2>$null | Out-Null'
    )


def drive_letter_choices() -> Tuple[str, ...]:
    return ("",) + tuple(f"{c}:" for c in "DEFGHIJKLMNOPQRSTUVWXYZ")
