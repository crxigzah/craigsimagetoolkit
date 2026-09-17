# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the desktop GUI. Build with:
#   pip install pyinstaller
#   pyinstaller gui/app.spec
# from the repo root, or see .github/workflows/build-gui.yml for the
# automated Windows build that runs on every tagged release.
import os

gui_dir = os.path.dirname(os.path.abspath(SPEC))
root_dir = os.path.dirname(gui_dir)

a = Analysis(
    ['app.py'],
    pathex=[
        gui_dir,
        os.path.join(root_dir, 'compress'),
        os.path.join(root_dir, 'resize'),
        os.path.join(root_dir, 'blur'),
    ],
    binaries=[],
    # presets.json has to sit at the same top level resize.py's frozen
    # __file__ resolves against -- see the frozen-path handling in
    # resize/resize.py's PRESETS_PATH.
    datas=[
        (os.path.join(root_dir, 'resize', 'presets.json'), '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='craigsimagetoolkit',
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
)
