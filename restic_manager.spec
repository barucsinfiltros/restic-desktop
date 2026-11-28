# -*- mode: python ; coding: utf-8 -*-
# Build (Windows / Linux):
#   pyinstaller restic_manager.spec
#
# App icon:
#   Windows → icons/app.ico  (EXE + taskbar branding)
#   Linux   → icons/app.png  (executable / desktop icon)
# Runtime window icon is resolved by ui.themes.app_window_icon() from the
# bundled icons/ folder (app.ico → app.png → app.svg).
#
# UPX is off on purpose: compressing the EXE often breaks / blanks the
# Explorer icon (especially after rename) even though the icon is embedded.

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve()
_ICON = str(
    ROOT / "icons" / ("app.ico" if sys.platform == "win32" else "app.png")
)

a = Analysis(
    [str(ROOT / 'restic_manager.py')],
    pathex=[],
    binaries=[(str(ROOT / 'restic/windows/restic.exe'), 'restic/windows')] if sys.platform == 'win32' else [],
    datas=[(str(ROOT / name), name) for name in ('icons', 'images')],
    hiddenimports=[
        'core',
        'core.history_db',
        'ui',
        'ui.themes',
        'ui.title_bar',
        'ui.framed_dialog',
        'ui.rounded_menu',
        'ui.icons',
        'ui.cards',
        'ui.charts',
        'ui.sidebar',
        'ui.dashboard',
        'ui.repositories',
        'ui.snapshots',
        'ui.restore',
        'ui.backup_jobs',
        'ui.retention',
        'ui.logs',
        'ui.settings',
        'ui.health_dialog',
        'ui.table_helpers',
        'ui.hover_tip',
        'core.health',
        'PySide6.QtSvg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'PIL',
        'tkinter',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ResticDesktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ICON,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ResticDesktop')
