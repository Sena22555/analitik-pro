# -*- mode: python ; coding: utf-8 -*-
# Сборка: pyinstaller AnalitikApp.spec  →  dist/Analitik Pro.app (macOS) или dist/Analitik Pro/ (Windows)
import sys

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('demo_data.csv', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['seaborn', 'scipy', 'sqlalchemy', 'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Analitik Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if sys.platform.startswith('win') else 'assets/icon.icns',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Analitik Pro',
)
app = BUNDLE(
    coll,
    name='Analitik Pro.app',
    icon='assets/icon.icns',
    bundle_identifier='com.sena22555.analitikpro',
)
