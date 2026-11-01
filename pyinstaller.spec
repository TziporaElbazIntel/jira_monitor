# -*- mode: python ; coding: utf-8 -*-
# Build with: pyinstaller pyinstaller.spec
# (equivalent to: pyinstaller --noconsole --onefile app/main.py --name JiraTrayMonitor)
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# pypac (proxy auto-detection) needs non-Python data files at runtime that
# PyInstaller doesn't pick up on its own, e.g. publicsuffixlist's
# public_suffix_list.dat and dukpy's bundled JS modules.
_package_data = []
for _pkg in ("publicsuffixlist", "pypac", "dukpy"):
    try:
        _package_data += collect_data_files(_pkg)
    except Exception:
        pass

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("app/assets", "app/assets"),  # bundles the real Jira logo PNG, if
                                       # present, so the frozen exe uses it
                                       # too (not just the source checkout).
    ] + _package_data,
    hiddenimports=[
        "pystray._win32",
        "pystray._xorg",
        "pystray._darwin",
        "plyer.platforms.win.notification",
        "plyer.platforms.linux.notification",
        "plyer.platforms.macosx.notification",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="JiraTrayMonitor",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    onefile=True,
)
