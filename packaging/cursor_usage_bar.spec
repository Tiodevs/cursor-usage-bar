import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT))
from cursor_usage_bar import __version__  # noqa: E402

NAME = "Cursor Usage Bar"
IS_MAC = sys.platform == "darwin"

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    hiddenimports=["cursor_usage_bar.mac_app"] if IS_MAC else ["cursor_usage_bar.windows_app", "pystray._win32"],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)

if IS_MAC:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False)
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME)
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        bundle_identifier="com.tiodevs.cursor-usage-bar",
        version=__version__,
        info_plist={
            "LSUIElement": True,
            "CFBundleShortVersionString": __version__,
            "NSHumanReadableCopyright": "MIT License",
        },
    )
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="CursorUsageBar", console=False)
