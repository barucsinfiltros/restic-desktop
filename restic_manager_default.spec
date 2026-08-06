# -*- mode: python ; coding: utf-8 -*-
# Alternate/default build spec — keep in sync with restic_manager.spec
# Build: pyinstaller restic_manager_default.spec

import sys
from pathlib import Path

_ICON = str(
    Path("icons") / ("app.ico" if sys.platform == "win32" else "app.png")
)

a = Analysis(
    ['restic_manager.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons')],
    hiddenimports=[
        'themes',
        'history_db',
        'title_bar',
        'framed_dialog',
        'rounded_menu',
        'ui',
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
        'ui.table_helpers',
        'PyQt6.QtSvg',
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
    a.binaries,
    a.datas,
    [],
    name='restic_manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
