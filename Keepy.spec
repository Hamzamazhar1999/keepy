# -*- mode: python ; coding: utf-8 -*-
#
# Keepy.spec - PyInstaller spec equivalent to:
#     pyinstaller --onefile --windowed --name Keepy keepy.py
#
# Power users can build with:
#     pyinstaller Keepy.spec
#
# Notes:
#   * Single-file bundle (the EXE collects binaries/datas/zipfiles directly).
#   * console=False  => --windowed (no console/terminal window).
#   * Keepy has no assets/data files (all art is drawn in code; the only user
#     file ~/.keepy/sounds.json is created at runtime), so datas is empty.
#   * tkinter is detected automatically; winsound is a stdlib builtin, so no
#     hidden imports are required.


block_cipher = None


a = Analysis(
    ['keepy.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --onefile: everything is passed to EXE (no separate COLLECT step).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Keepy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # --windowed: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
