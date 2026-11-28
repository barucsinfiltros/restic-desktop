"""Locate application resources, persistent data and the Restic executable."""

import os
from pathlib import Path
import shutil
import sys


RESOURCE_DIR = Path(__file__).resolve().parent.parent


def data_directory() -> Path:
    if getattr(sys, "frozen", False) and os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return local / "ResticDesktop"
    return RESOURCE_DIR


def resolve_restic(executable: str | None = None, *, cwd: Path | None = None,
                   search_path: str | None = None) -> str:
    """Prefer the bundled binary in automatic mode; honor explicit overrides."""
    name = (executable or "").strip() or "restic"
    base = cwd or RESOURCE_DIR
    path = Path(name)
    if name == "restic":
        if os.name == "nt":
            bundled = RESOURCE_DIR / "restic" / "windows" / "restic.exe"
            if bundled.is_file():
                return str(bundled)
    if path.is_absolute() or "/" in name or "\\" in name:
        candidates = (base / path,)
    else:
        folders = search_path if search_path is not None else os.environ.get("PATH", os.defpath)
        candidates = (base / folder / name for folder in folders.split(os.pathsep) if folder)
    for candidate in candidates:
        found = shutil.which(str(candidate))
        if found and (os.name != "nt" or Path(found).suffix.lower() == ".exe"):
            return found
    raise FileNotFoundError(
        f"No se encontró un ejecutable compatible de Restic ({name}). "
        "Reinstala la distribución completa o selecciona el ejecutable en Settings."
    )
