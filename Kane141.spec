# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

kivy_datas = collect_data_files("kivy")
kivymd_datas = collect_data_files("kivymd")

hiddenimports = [
    "screens",
    "screens.main",
    "screens.settings",

    "widgets",
    "widgets.core",
    "widgets.game",
    "widgets.gamelist",
    "widgets.navigation",
    "widgets.searchbar",
    "widgets.border",

    "utils",
    "utils.fetch_feed",
    "utils.scraper",
    "utils.settings",
    "utils.sysreq",
    "utils.thread_with_return",

    "database",
    "database.database",
]
a = Analysis(
    ["src/app.py"],
    pathex=[".", "src"],
    binaries=[],
    datas=[
        ("src/database/games.db", "database"),
        ("src/settings.yaml", "."),
        ("src/screens.yaml", "."),
        ("Kane141.png", "."),
    ]
    + kivy_datas
    + kivymd_datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="Kane141",
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
    icon=["Kane141.png"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Kane141",
)
