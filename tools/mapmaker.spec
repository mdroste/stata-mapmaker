# Run via tools/build_bundle.py using the locked build environment.
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "python/mapmaker_cli.py")],
    pathex=[str(root / "python")],
    binaries=[], datas=[],
    hiddenimports=["matplotlib.backends.backend_pdf", "matplotlib.backends.backend_svg"],
    hookspath=[], hooksconfig={"matplotlib": {"backends": ["Agg"]}},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="mapmaker-render",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="mapmaker-render")
