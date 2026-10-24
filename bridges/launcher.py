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
except Exception as exc:  # said by main() on the `error` line, with its traceback
    BRIDGE_MODULES = {}
    _MANIFEST_ERROR = exc

#: The codes of the launcher's own failures (`taktik/core/contract/error_codes.py`): it was named no
#: bridge, or one the manifest does not list; the manifest does not read.
UNKNOWN_BRIDGE = "UNKNOWN_BRIDGE"
BRIDGE_MANIFEST_UNREADABLE = "BRIDGE_MANIFEST_UNREADABLE"


def _refuse(message: str, error_code: str) -> None:
    """End the launch on the contract's `error` line (words, code), before any bridge is imported."""
    from bridges.common.ipc import IPC
    IPC().error(message, error_code=error_code)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        _refuse("Usage: taktik_launcher.exe <bridge_name> [args...]", error_code=UNKNOWN_BRIDGE)

    if _MANIFEST_ERROR is not None:
        # The exception was raised at import: `send_run_error` puts its traceback on the line.
        from bridges.common.entrypoint import send_run_error
        send_run_error(f"Bridge manifest unreadable: {type(_MANIFEST_ERROR).__name__}: {_MANIFEST_ERROR}",
                       _MANIFEST_ERROR, error_code=BRIDGE_MANIFEST_UNREADABLE)
        sys.exit(1)

    bridge_name = sys.argv[1]

    if bridge_name not in BRIDGE_MODULES:
        _refuse(f"Unknown bridge: '{bridge_name}'. Available: {list(BRIDGE_MODULES.keys())}", error_code=UNKNOWN_BRIDGE)

    # Every bridge goes through here, so this is the one place a floor can be put under all of
    # them: an uncaught exception now reports a machine-readable UNHANDLED_EXCEPTION event with its
    # traceback instead of dying with nothing but an exit code, and a module that does not import
    # (the bridge below included) a PYTHON_IMPORT_ERROR one.
    from bridges.common.crash_hooks import install_crash_hooks
    install_crash_hooks(bridge_name)

    # Same floor, other failure: the desktop app dies and the bridge keeps driving the phone with
    # nobody to read its events or stop it. Started before the bridge is imported so the owner is
    # watched from the first second; a no-op when the bot runs on its own (no TAKTIK_DESKTOP_PID).
    from bridges.common.owner_watchdog import start_owner_watchdog
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
