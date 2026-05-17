# Build with:
#   pyinstaller packaging/pyinstaller/playlistgit.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


block_cipher = None
repo_root = Path(SPECPATH).parents[1]

a = Analysis(
    [str(repo_root / "src/playlistgit/desktop.py")],
    pathex=[str(repo_root / "src"), str(repo_root)],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("ytmusicapi") + collect_submodules("spotipy"),
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Playlist Git",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Playlist Git",
)

app = BUNDLE(
    coll,
    name="Playlist Git.app",
    icon=None,
    bundle_identifier="app.playlistgit.desktop",
)
