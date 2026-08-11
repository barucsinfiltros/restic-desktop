"""rclone helpers for cloud repositories (restic rclone: backend)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from typing import Dict, List, Optional, Tuple

# User-facing provider id → label → rclone backend type name
CLOUD_PROVIDERS: Tuple[Tuple[str, str, str], ...] = (
    ("onedrive", "OneDrive", "onedrive"),
    ("google_drive", "Google Drive", "drive"),
    ("dropbox", "Dropbox", "dropbox"),
    ("s3", "Amazon S3", "s3"),
    ("b2", "Backblaze B2", "b2"),
    ("azure", "Azure Blob", "azureblob"),
    ("wasabi", "Wasabi", "s3"),
    ("rest", "REST server (HTTPS)", ""),
    ("other", "Other (existing remote)", ""),
)


def provider_label(provider_id: str) -> str:
    for pid, label, _backend in CLOUD_PROVIDERS:
        if pid == provider_id:
            return label
    return provider_id or "Cloud"


def provider_rclone_type(provider_id: str) -> str:
    for pid, _label, backend in CLOUD_PROVIDERS:
        if pid == provider_id:
            return backend
    return ""


def app_rclone_config_path(base_dir: Optional[str] = None) -> str:
    root = base_dir or os.getcwd()
    return os.path.join(root, "rclone.conf")


def resolve_rclone_path(settings_get) -> str:
    """settings_get: callable like settings_manager.get"""
    configured = ""
    try:
        configured = (settings_get("rclone_path") or "").strip()
    except Exception:
        configured = ""
    return configured or "rclone"


def rclone_process_env(
    *,
    rclone_path: str = "",
    config_path: str = "",
    base: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    env = dict(base if base is not None else os.environ)
    if config_path:
        env["RCLONE_CONFIG"] = config_path
    bin_dir = os.path.dirname(os.path.abspath(rclone_path)) if rclone_path else ""
    if bin_dir and os.path.isdir(bin_dir):
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


def run_rclone(
    rclone_path: str,
    args: List[str],
    *,
    env: Optional[Dict[str, str]] = None,
    timeout: int = 120,
    creationflags: int = 0,
) -> Tuple[bool, str, str]:
    cmd = [rclone_path, *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env or os.environ.copy(),
            timeout=timeout,
            creationflags=creationflags,
        )
        return (
            proc.returncode == 0,
            (proc.stdout or "").strip(),
            (proc.stderr or "").strip(),
        )
    except FileNotFoundError:
        return False, "", f"rclone not found: {rclone_path}"
    except subprocess.TimeoutExpired:
        return False, "", "rclone command timed out"
    except Exception as exc:
        return False, "", str(exc)


def rclone_version(
    rclone_path: str, *, env: Optional[Dict[str, str]] = None
) -> Optional[str]:
    ok, stdout, stderr = run_rclone(rclone_path, ["version"], env=env, timeout=30)
    text = stdout or stderr
    if not ok and not text:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("rclone "):
            return line
    return text.splitlines()[0].strip() if text else None


def list_rclone_remotes(
    rclone_path: str, *, env: Optional[Dict[str, str]] = None
) -> List[Tuple[str, str]]:
    """Return [(remote_name_without_colon, type), ...]."""
    ok, stdout, _stderr = run_rclone(
        rclone_path, ["config", "dump"], env=env, timeout=60
    )
    remotes: List[Tuple[str, str]] = []
    if ok and stdout:
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                for name, cfg in data.items():
                    if not name or name.startswith("["):
                        continue
                    rtype = ""
                    if isinstance(cfg, dict):
                        rtype = str(cfg.get("type") or "")
                    remotes.append((str(name).rstrip(":"), rtype))
                remotes.sort(key=lambda x: x[0].lower())
                return remotes
        except json.JSONDecodeError:
            pass

    ok, stdout, _stderr = run_rclone(
        rclone_path, ["listremotes"], env=env, timeout=60
    )
    if not ok:
        return []
    for line in (stdout or "").splitlines():
        name = line.strip().rstrip(":")
        if name:
            remotes.append((name, ""))
    return remotes


def filter_remotes_for_provider(
    remotes: List[Tuple[str, str]], provider_id: str
) -> List[Tuple[str, str]]:
    backend = provider_rclone_type(provider_id)
    if provider_id in ("other", "rest") or not backend:
        return remotes
    matched = [(n, t) for n, t in remotes if (t or "").lower() == backend.lower()]
    return matched if matched else remotes


def build_rclone_repo_url(remote: str, remote_path: str = "") -> str:
    remote = (remote or "").strip().rstrip(":")
    path = (remote_path or "").strip().lstrip("/")
    if not remote:
        return ""
    if path:
        return f"rclone:{remote}:{path}"
    return f"rclone:{remote}:"


def parse_rclone_location(location: str) -> Dict[str, str]:
    loc = (location or "").strip()
    if not loc.startswith("rclone:"):
        return {"remote": "", "path": ""}
    rest = loc[len("rclone:") :]
    if ":" in rest:
        remote, path = rest.split(":", 1)
        return {"remote": remote.rstrip(":"), "path": path.lstrip("/")}
    return {"remote": rest.rstrip(":"), "path": ""}


def new_remote_name(provider_id: str) -> str:
    short = re.sub(r"[^a-z0-9]+", "", (provider_id or "cloud").lower())[:12] or "cloud"
    return f"rd_{short}_{uuid.uuid4().hex[:6]}"


def build_unc_path(server: str, share: str, subpath: str = "") -> str:
    server = (server or "").strip().strip("\\/")
    share = (share or "").strip().strip("\\/")
    sub = (subpath or "").strip().replace("/", "\\").strip("\\")
    if not server or not share:
        return ""
    base = f"\\\\{server}\\{share}"
    return f"{base}\\{sub}" if sub else base


def _hidden_creationflags() -> int:
    """Run rclone without showing a console window (Windows)."""
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def extract_authorize_token(stdout: str) -> str:
    """Parse the config_token blob from ``rclone authorize`` output."""
    text = (stdout or "").strip()
    if not text:
        return ""
    marker_start = "Paste the following into your remote machine --->"
    marker_end = "<---End paste"
    if marker_start in text and marker_end in text:
        return text.split(marker_start, 1)[1].split(marker_end, 1)[0].strip()
    # Newer rclone may print JSON directly
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line or line.startswith("NOTICE:"):
            continue
        if line.startswith("{") or line.startswith("eyJ") or len(line) > 40:
            return line
    return text


def _combine_rclone_output(stdout: str, stderr: str) -> str:
    parts = [(stdout or "").strip(), (stderr or "").strip()]
    return "\n".join(part for part in parts if part)


def delete_rclone_remote(
    rclone_path: str,
    remote_name: str,
    *,
    env: Optional[Dict[str, str]] = None,
) -> None:
    """Remove a remote if present (best-effort)."""
    names = {n for n, _t in list_rclone_remotes(rclone_path, env=env)}
    if remote_name not in names:
        return
    run_rclone(
        rclone_path,
        ["config", "delete", remote_name],
        env=env,
        timeout=30,
        creationflags=_hidden_creationflags(),
    )


def _parse_rclone_config_json(stdout: str) -> Optional[dict]:
    """Parse JSON emitted by ``rclone config create/update --non-interactive``."""
    text = (stdout or "").strip()
    if not text:
        return None
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _example_value(example: object) -> str:
    if isinstance(example, dict):
        return str(example.get("Value") or example.get("value") or "")
    return str(example or "")


def _example_help(example: object) -> str:
    if isinstance(example, dict):
        return str(example.get("Help") or example.get("help") or "")
    return ""


def _pick_onedrive_drive_id(examples: object, default: object = "") -> str:
    """Choose the main OneDrive library from rclone's drive list."""
    if not isinstance(examples, list):
        return str(default or "")
    candidates: List[Tuple[int, str]] = []
    for ex in examples:
        val = _example_value(ex)
        if not val:
            continue
        label = _example_help(ex).lower()
        score = 0
        if "onedrive" in label:
            score += 10
        if "personal" in label:
            score += 5
        if "business" in label:
            score += 3
        if any(
            skip in label
            for skip in (
                "personal vault",
                "odcmetadata",
                "preservation",
                "hold library",
                "bundles_",
            )
        ):
            score -= 25
        if val == str(default or ""):
            score += 2
        if label.strip() in ("onedrive (personal)", "onedrive"):
            score += 15
        candidates.append((score, val))
    if not candidates:
        return str(default or "")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _pick_rclone_config_answer(
    data: dict,
    *,
    config_token: str = "",
    provider_id: str = "",
) -> Optional[str]:
    """Auto-answer rclone non-interactive config prompts after OAuth."""
    opt = data.get("Option") if isinstance(data.get("Option"), dict) else {}
    name = str(opt.get("Name") or "").lower()
    help_text = str(opt.get("Help") or "").lower()
    state = str(data.get("State") or "").lower()

    # OAuth chain: islocal → remote → authorize (needs config_token, NOT false).
    if name == "config_token" or "oauth-authorize" in state:
        return config_token or None
    if "oauth-islocal" in state:
        return "false"
    if "oauth-remote" in state:
        return ""

    if provider_id == "onedrive":
        if "choose_type" in state or "choose_type" in name or "config_type" in name:
            return "onedrive"
        if "driveid" in name or "config_driveid" in name or "driveid" in state:
            picked = _pick_onedrive_drive_id(opt.get("Examples"), opt.get("Default"))
            if picked:
                return picked
            default = opt.get("Default")
            return str(default) if default is not None else ""
        if "driveid_final_end" in name or "driveid_final_end" in state:
            return "true"

    if "confirm" in name and opt.get("Type") == "bool":
        return "true"
    if opt.get("Type") == "bool":
        return "true"
    if "yes" in help_text and "no" in help_text:
        return "true"
    default = opt.get("Default")
    if default is not None and default != "":
        return str(default)
    return None


def _drive_rclone_noninteractive_config(
    rclone_path: str,
    remote_name: str,
    *,
    env: Optional[Dict[str, str]] = None,
    initial_output: str = "",
    backend_type: str = "onedrive",
    use_create: bool = True,
    config_token: str = "",
    provider_id: str = "",
    max_steps: int = 24,
) -> Tuple[bool, str]:
    """
    Complete OneDrive setup via rclone's non-interactive config prompts.

    Must continue with ``config create --continue`` when the flow started from
    ``config create`` (``config update`` will loop without saving the token).
    """
    flags = _hidden_creationflags()
    if use_create:
        base = ["config", "create", remote_name, backend_type]
    else:
        base = ["config", "update", remote_name]

    data = _parse_rclone_config_json(initial_output)
    args: List[str] = base + ["--non-interactive"]
    last_output = initial_output
    last_question = ""

    for _step in range(max_steps):
        if data is None:
            ok, stdout, stderr = run_rclone(
                rclone_path,
                args,
                env=env,
                timeout=120,
                creationflags=flags,
            )
            last_output = _combine_rclone_output(stdout, stderr)
            data = _parse_rclone_config_json(last_output)
            if data is None:
                if ok:
                    return True, ""
                return False, (last_output or "OneDrive setup failed.").strip()

        if data.get("Error"):
            return False, str(data["Error"])

        state = str(data.get("State") or "").strip()
        if not state:
            return True, ""

        opt = data.get("Option") if isinstance(data.get("Option"), dict) else {}
        last_question = str(opt.get("Name") or state)

        answer = _pick_rclone_config_answer(
            data,
            config_token=config_token,
            provider_id=provider_id,
        )
        if answer is None:
            detail = last_output[-800:] if last_output else ""
            return False, (
                f"OneDrive setup needs manual input ({last_question}). "
                "Try Sign in again."
                + (f"\n\n{rclone_detail_snippet(detail)}" if detail else "")
            )

        args = base + [
            "--continue",
            "--state",
            state,
            "--result",
            answer,
            "--non-interactive",
        ]
        data = None

    detail = last_output[-800:] if last_output else ""
    msg = "OneDrive setup did not finish. Try Sign in again."
    if last_question:
        msg = f"{msg}\n\nLast step: {last_question}."
    snippet = rclone_detail_snippet(detail)
    if snippet:
        msg = f"{msg}\n\n{snippet}"
    return False, msg


def rclone_detail_snippet(text: str, limit: int = 400) -> str:
    """Short, user-safe excerpt from rclone output for error dialogs."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    lines = [
        line
        for line in cleaned.splitlines()
        if line.strip()
        and not line.strip().lower().startswith("notice:")
    ]
    excerpt = "\n".join(lines[-8:])
    if len(excerpt) > limit:
        excerpt = excerpt[-limit:]
    return excerpt.strip()


def _finalize_onedrive_remote_with_update(
    rclone_path: str,
    remote_name: str,
    *,
    env: Optional[Dict[str, str]] = None,
    config_token: str = "",
) -> Tuple[bool, str]:
    """
    Fallback: if token exists but drive_id is missing, run config update flow.
    """
    return _drive_rclone_noninteractive_config(
        rclone_path,
        remote_name,
        env=env,
        use_create=False,
        config_token=config_token,
        provider_id="onedrive",
    )


def _remote_has_token(
    rclone_path: str, remote_name: str, *, env: Optional[Dict[str, str]] = None
) -> bool:
    ok, stdout, _stderr = run_rclone(
        rclone_path, ["config", "dump"], env=env, timeout=60, creationflags=_hidden_creationflags()
    )
    if not ok or not stdout:
        return False
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    cfg = data.get(remote_name) if isinstance(data, dict) else None
    if not isinstance(cfg, dict):
        return False
    return bool(cfg.get("token"))


def _onedrive_remote_ready(
    rclone_path: str, remote_name: str, *, env: Optional[Dict[str, str]] = None
) -> bool:
    ok, stdout, _stderr = run_rclone(
        rclone_path, ["config", "dump"], env=env, timeout=60, creationflags=_hidden_creationflags()
    )
    if not ok or not stdout:
        return False
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    cfg = data.get(remote_name) if isinstance(data, dict) else None
    if not isinstance(cfg, dict):
        return False
    return bool(cfg.get("token") and cfg.get("drive_id") and cfg.get("drive_type"))


def create_remote_via_authorize(
    rclone_path: str,
    remote_name: str,
    backend_type: str,
    *,
    env: Optional[Dict[str, str]] = None,
    provider_id: str = "",
    timeout: int = 600,
) -> Tuple[bool, str]:
    """
    Headless OAuth: ``rclone authorize`` (opens browser, no console) then
    ``rclone config create … config_token … --non-interactive``.
    """
    if not backend_type:
        return False, "No backend type for this provider."

    flags = _hidden_creationflags()
    ok, stdout, stderr = run_rclone(
        rclone_path,
        ["authorize", backend_type],
        env=env,
        timeout=timeout,
        creationflags=flags,
    )
    if not ok:
        detail = (stderr or stdout or "").strip()
        if "context canceled" in detail.lower() or "access denied" in detail.lower():
            return False, "Sign-in was cancelled or not completed."
        return False, detail or "Authorization failed."

    token = extract_authorize_token(stdout)
    if not token:
        return False, "No authorization token received. Complete sign-in in the browser."

    create_args = [
        "config",
        "create",
        remote_name,
        backend_type,
        "config_token",
        token,
        "--non-interactive",
    ]

    ok2, out2, err2 = run_rclone(
        rclone_path,
        create_args,
        env=env,
        timeout=120,
        creationflags=flags,
    )
    create_output = _combine_rclone_output(out2, err2)
    create_json = _parse_rclone_config_json(create_output)
    if not ok2 and not create_json and not create_output:
        return False, (err2 or "Failed to save cloud connection.").strip()

    if provider_id == "onedrive":
        if create_json:
            ok3, err3 = _drive_rclone_noninteractive_config(
                rclone_path,
                remote_name,
                env=env,
                initial_output=create_output,
                backend_type=backend_type,
                use_create=True,
                config_token=token,
                provider_id=provider_id,
            )
        elif _onedrive_remote_ready(rclone_path, remote_name, env=env):
            ok3, err3 = True, ""
        else:
            ok3, err3 = _drive_rclone_noninteractive_config(
                rclone_path,
                remote_name,
                env=env,
                initial_output=create_output,
                backend_type=backend_type,
                use_create=False,
                config_token=token,
                provider_id=provider_id,
            )
        if not ok3:
            delete_rclone_remote(rclone_path, remote_name, env=env)
            return False, err3
        if not _onedrive_remote_ready(rclone_path, remote_name, env=env):
            ok4, err4 = _finalize_onedrive_remote_with_update(
                rclone_path, remote_name, env=env, config_token=token
            )
            if not ok4 or not _onedrive_remote_ready(rclone_path, remote_name, env=env):
                delete_rclone_remote(rclone_path, remote_name, env=env)
                return False, err4 or (
                    "OneDrive sign-in finished but drive selection did not complete. "
                    "Try Sign in again."
                )
    elif create_json or (not ok2 and create_output):
        ok3, err3 = _drive_rclone_noninteractive_config(
            rclone_path,
            remote_name,
            env=env,
            initial_output=create_output,
            backend_type=backend_type,
            use_create=True,
            config_token=token,
            provider_id=provider_id,
        )
        if not ok3:
            delete_rclone_remote(rclone_path, remote_name, env=env)
            return False, err3
        if not _remote_has_token(rclone_path, remote_name, env=env):
            delete_rclone_remote(rclone_path, remote_name, env=env)
            return False, "Sign-in finished but the connection was not saved."
    elif not ok2:
        delete_rclone_remote(rclone_path, remote_name, env=env)
        return False, (err2 or out2 or "Failed to save cloud connection.").strip()

    # Verify remote exists
    names = {n for n, _t in list_rclone_remotes(rclone_path, env=env)}
    if remote_name not in names:
        return False, "Sign-in finished but the connection was not saved."
    return True, ""


def launch_rclone_config_create(
    rclone_path: str,
    remote_name: str,
    backend_type: str,
    *,
    env: Optional[Dict[str, str]] = None,
    creationflags: int = 0,
) -> Tuple[bool, str]:
    """Deprecated: interactive console config. Prefer create_remote_via_authorize."""
    if not backend_type:
        return False, "No backend type for this provider."
    cmd = [rclone_path, "config", "create", remote_name, backend_type]
    if backend_type == "s3" and remote_name.startswith("rd_wasabi"):
        cmd.append("provider=Wasabi")
    try:
        flags = creationflags
        if os.name == "nt":
            flags |= getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(
            cmd,
            env=env or os.environ.copy(),
            creationflags=flags,
        )
        return True, (
            f"Opened rclone sign-in for remote '{remote_name}'.\n"
            "Complete the steps in the new window (browser login if asked),\n"
            "then click Refresh remotes."
        )
    except FileNotFoundError:
        return False, f"rclone not found: {rclone_path}"
    except Exception as exc:
        return False, str(exc)


def is_cloud_repo(repo: Optional[dict]) -> bool:
    if not repo:
        return False
    path = (repo.get("path") or "").strip()
    if path.startswith("rclone:"):
        return True
    t = (repo.get("type") or "").lower()
    if t not in ("cloud", "rclone"):
        return False
    provider = (repo.get("cloud_provider") or "").lower()
    # Native object storage is type=cloud but not rclone
    if provider in ("s3", "b2", "azure", "wasabi", "rest"):
        return False
    return True


def uses_rclone_backend(repo: Optional[dict]) -> bool:
    return is_cloud_repo(repo)


def build_object_storage_url(
    provider: str,
    bucket: str,
    prefix: str = "",
    *,
    endpoint: str = "",
) -> str:
    bucket = (bucket or "").strip().strip("/")
    prefix = (prefix or "").strip().strip("/")
    endpoint = (endpoint or "").strip().rstrip("/")
    if not bucket:
        return ""
    if provider == "b2":
        return f"b2:{bucket}:/{prefix}" if prefix else f"b2:{bucket}"
    if provider == "azure":
        return f"azure:{bucket}:/{prefix}" if prefix else f"azure:{bucket}"
    if provider == "wasabi":
        host = endpoint or "s3.wasabisys.com"
    else:
        host = endpoint or "s3.amazonaws.com"
    if prefix:
        return f"s3:{host}/{bucket}/{prefix}"
    return f"s3:{host}/{bucket}"


def apply_object_storage_env(
    repo: dict, env: Dict[str, str], *, password_manager=None
) -> None:
    """Set AWS/B2/Azure env vars for native restic object-storage repos."""
    provider = (repo.get("cloud_provider") or "").lower()
    if provider not in ("s3", "b2", "azure", "wasabi"):
        return
    key_id = (repo.get("object_key_id") or "").strip()
    secret = repo.get("object_secret_plain")
    if secret is None:
        enc = repo.get("object_secret") or ""
        secret = ""
        if enc and password_manager is not None:
            try:
                secret = password_manager.decrypt(enc)
            except Exception:
                secret = ""
    secret = secret or ""
    region = (repo.get("object_region") or "").strip()
    if provider in ("s3", "wasabi"):
        if key_id:
            env["AWS_ACCESS_KEY_ID"] = key_id
        if secret:
            env["AWS_SECRET_ACCESS_KEY"] = secret
        if region:
            env["AWS_DEFAULT_REGION"] = region
    elif provider == "b2":
        if key_id:
            env["B2_ACCOUNT_ID"] = key_id
        if secret:
            env["B2_ACCOUNT_KEY"] = secret
    elif provider == "azure":
        if key_id:
            env["AZURE_ACCOUNT_NAME"] = key_id
        if secret:
            env["AZURE_ACCOUNT_KEY"] = secret
