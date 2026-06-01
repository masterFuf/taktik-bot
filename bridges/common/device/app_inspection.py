"""Inspection helpers for bridge-managed mobile apps."""

import subprocess
from typing import Any, Optional

from loguru import logger


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


def get_installed_app_version(device_id: str, package_name: str, platform: str) -> Optional[str]:
    """Detect the installed app version via ADB dumpsys."""
    try:
        result = subprocess.run(
            ["adb", "-s", device_id, "shell", "dumpsys", "package", package_name],
            capture_output=True,
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
