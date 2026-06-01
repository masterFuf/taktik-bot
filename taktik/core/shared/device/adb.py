"""Shared ADB shell helpers for device/runtime owners."""

import subprocess

from loguru import logger


def run_adb_shell(device_id: str, command: str) -> str:
    """
    Execute an ADB shell command using adbutils, with subprocess fallback.

    Args:
        device_id: ADB device serial/ID.
        command: Shell command to execute without the `adb shell` prefix.

    Returns:
        Command output as string, or an empty string on error.
    """
    try:
        from adbutils import adb

        device = adb.device(serial=device_id)
        return device.shell(command)
    except ImportError:
        try:
            result = subprocess.run(
                ["adb", "-s", device_id, "shell"] + command.split(),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception as exc:
            logger.debug(f"ADB subprocess error: {exc}")
            return ""
    except Exception as exc:
        logger.debug(f"ADB shell error: {exc}")
        return ""


__all__ = ["run_adb_shell"]
