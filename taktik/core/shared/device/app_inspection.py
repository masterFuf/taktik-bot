"""ADB app-inspection primitives: is it installed, is it foreground, which version.

Moved from `bridges/common/device/` to its AGENTS owner: these are pure ADB shell
primitives (`run_adb_shell_process` + parsing), and the standalone CLI needs the
version reader to apply selector version overrides without importing a desktop
bridge adapter. `bridges/common/device/app_inspection.py` re-exports for compat.
"""

from typing import Any, Optional

from loguru import logger
from taktik.core.shared.device.adb import run_adb_shell_process


def is_app_running(device: Any, package_name: str, platform: str) -> bool:
    """Check whether a package is currently in the foreground."""
    if device is None:
        return False
    try:
        current_app = device.app_current()
        return current_app.get("package") == package_name
    except Exception as exc:
        logger.warning(f"Could not check if {platform} is running: {exc}")
        return False


def is_package_installed(device_id: str, package_name: str) -> bool:
    """Is the package REALLY installed for the current user?

    `dumpsys package` still prints the package record (versionName included) for an app that is
    NOT installed: a system app whose updates were removed, `pm uninstall -k`, an app installed on
    another Android profile, a disabled package. `pm list packages --user 0` lists what is actually
    installed. The comparison is an EXACT line match: `pm list packages` filters by SUBSTRING, so a
    clone-only device would otherwise look like it had the official app.
    """
    try:
        result = run_adb_shell_process(
            device_id,
            ["pm", "list", "packages", "--user", "0", package_name],
            text=True,
            timeout=10,
        )
        installed = {
            line.strip().replace("package:", "").strip()
            for line in (result.stdout or "").splitlines()
        }
        return package_name in installed
    except Exception as exc:
        logger.warning(f"[AppService] Failed to check if {package_name} is installed: {exc}")
        return False


def get_installed_app_version(device_id: str, package_name: str, platform: str) -> Optional[str]:
    """Detect the installed app version via ADB dumpsys.

    Returns None when the app is not installed — the version alone cannot answer that (see
    is_package_installed): dumpsys happily reports a version for an uninstalled package.
    """
    if not is_package_installed(device_id, package_name):
        logger.info(f"[AppService] {platform} is not installed on {device_id}")
        return None
    try:
        result = run_adb_shell_process(
            device_id,
            ["dumpsys", "package", package_name],
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("versionName="):
                version = line.split("=", 1)[1].strip()
                logger.info(f"[AppService] {platform} installed version: {version}")
                return version
        logger.warning(f"[AppService] versionName not found in dumpsys output for {package_name}")
        return None
    except Exception as exc:
        logger.warning(f"[AppService] Failed to detect app version: {exc}")
        return None
