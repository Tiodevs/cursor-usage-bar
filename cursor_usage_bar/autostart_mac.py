import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "com.tiodevs.cursor-usage-bar"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def app_bundle() -> Path | None:
    """Path to the running .app, or None when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    bundle = Path(sys.executable).resolve().parents[2]
    return bundle if bundle.suffix == ".app" else None


def is_enabled() -> bool:
    return PLIST.exists()


def enable() -> None:
    bundle = app_bundle()
    if bundle is None:
        raise RuntimeError("Disponível só no app empacotado")
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    with PLIST.open("wb") as f:
        plistlib.dump(
            {
                "Label": LABEL,
                "ProgramArguments": ["/usr/bin/open", "-a", str(bundle)],
                "RunAtLoad": True,
            },
            f,
        )


def disable() -> None:
    if PLIST.exists():
        subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
        PLIST.unlink()
