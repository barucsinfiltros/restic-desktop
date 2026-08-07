# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller license_generator_gui.spec
#
# Matches restic_manager chrome (ui.themes Chalk + icons). Keep this tool
# private — do not distribute to end users.

import sys
from pathlib import Path

_ICON = str(
    Path("icons") / ("app.ico" if sys.platform == "win32" else "app.png")
)

a = Analysis(
    ['license_generator_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons')],
    hiddenimports=[
        'ui',
        'ui.themes',
        'ui.title_bar',
        'ui.framed_dialog',
        'ui.cards',
        'ui.icons',
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
    name='license_generator_gui',
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
