# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the desktop GUI. Build with:
#   pip install pyinstaller
#   pyinstaller gui/app.spec
# from the repo root, or see .github/workflows/build-gui.yml for the
# automated Windows build that runs on every tagged release.
import os

from PyInstaller.utils.hooks import copy_metadata

gui_dir = os.path.dirname(os.path.abspath(SPEC))
root_dir = os.path.dirname(gui_dir)

# pymatting/__init__.py reads its own version with
# importlib.metadata.version(__name__) at import time -- PyInstaller
# doesn't bundle a package's .dist-info metadata by default, so without
# this the frozen exe hits "No package metadata was found for
# pymatting" the moment it imports rembg, before the window even opens.
datas = copy_metadata('pymatting')
datas += [
    # presets.json has to sit at the same top level resize.py's frozen
    # __file__ resolves against -- see the frozen-path handling in
    # resize/resize.py's PRESETS_PATH.
    (os.path.join(root_dir, 'resize', 'presets.json'), '.'),
]

a = Analysis(
    ['app.py'],
    pathex=[
        gui_dir,
        os.path.join(root_dir, 'compress'),
        os.path.join(root_dir, 'resize'),
        os.path.join(root_dir, 'blur'),
    ],
    binaries=[],
    datas=datas,
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
