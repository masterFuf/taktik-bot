"""
TAKTIK Bridge Launcher
======================
Single executable that routes to the appropriate bridge based on the first
command-line argument.

Instead of shipping 22 separate ~52 MB PyInstaller executables (total ~1.1 GB),
we compile ONE launcher that includes all bridge modules. The bridge list is
`bridges.manifest.json`, read at start; the build scripts read the same file.

Usage:
    taktik_launcher.exe <bridge_name> [bridge_args...]

Example:
    taktik_launcher.exe desktop_bridge
    taktik_launcher.exe tiktok_bridge
"""

import sys
import json
from pathlib import Path


BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))


MANIFEST_NAME = "bridges.manifest.json"


def _manifest_candidates() -> list[Path]:
    """Where the manifest sits: beside this file in a checkout, under `bridges/` in a build."""
    here = Path(__file__).resolve().parent
    candidates = [here / MANIFEST_NAME, here / "bridges" / MANIFEST_NAME]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidates.append(Path(bundle) / "bridges" / MANIFEST_NAME)
    return candidates


def load_bridge_modules() -> dict[str, str]:
    """Bridge name -> module path, read from `bridges.manifest.json` (the only list)."""
    for candidate in _manifest_candidates():
        if candidate.is_file():
            manifest = json.loads(candidate.read_text(encoding="utf-8-sig"))
            modules: dict[str, str] = {}
            for platform_bridges in manifest.values():
                modules.update(platform_bridges)
            return modules
    raise FileNotFoundError(f"{MANIFEST_NAME} not found in {[str(c) for c in _manifest_candidates()]}")


try:
    BRIDGE_MODULES: dict[str, str] = load_bridge_modules()
    _MANIFEST_ERROR = None
except Exception as exc:  # reported by main() as a JSON event, not a traceback
    BRIDGE_MODULES = {}
    _MANIFEST_ERROR = f"{type(exc).__name__}: {exc}"


def main():
    if len(sys.argv) < 2:
        error = {"type": "error", "message": "Usage: taktik_launcher.exe <bridge_name> [args...]"}
        print(json.dumps(error), flush=True)
        sys.exit(1)

    if _MANIFEST_ERROR and not BRIDGE_MODULES:
        error = {"type": "error", "message": f"Bridge manifest unreadable: {_MANIFEST_ERROR}"}
        print(json.dumps(error), flush=True)
        sys.exit(1)

    bridge_name = sys.argv[1]

    if bridge_name not in BRIDGE_MODULES:
        error = {"type": "error", "message": f"Unknown bridge: '{bridge_name}'. Available: {list(BRIDGE_MODULES.keys())}"}
        print(json.dumps(error), flush=True)
        sys.exit(1)

    # Every bridge goes through here, so this is the one place a floor can be put under all of
    # them: an uncaught exception (including one raised while importing the bridge below) now
    # reports a machine-readable UNHANDLED_EXCEPTION event with its traceback instead of dying
    # with nothing but an exit code.
    from bridges.common.runtime.crash_hooks import install_crash_hooks
    install_crash_hooks(bridge_name)

    # Same floor, other failure: the desktop app dies and the bridge keeps driving the phone with
    # nobody to read its events or stop it. Started before the bridge is imported so the owner is
    # watched from the first second; a no-op when the bot runs on its own (no TAKTIK_DESKTOP_PID).
    from bridges.common.runtime.owner_watchdog import start_owner_watchdog
    start_owner_watchdog(bridge_name)

    # Shift argv so the bridge sees itself as the "script":
    # Before: ["taktik_launcher.exe", "desktop_bridge", ...]
    # After:  ["desktop_bridge", ...]
    sys.argv = sys.argv[1:]

    # Lazy import — only loads the requested bridge and its deps
    import importlib
    module = importlib.import_module(BRIDGE_MODULES[bridge_name])
    module.main()


if __name__ == "__main__":
    main()
