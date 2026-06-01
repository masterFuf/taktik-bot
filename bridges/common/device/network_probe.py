"""Network inspection helpers for bridge device runtimes."""

from loguru import logger

from taktik.core.shared.device.adb import run_adb_shell


def get_device_external_ip(device_id: str) -> str:
    """
    Fetch the external/carrier IP of the device via ADB shell.

    Tries curl first, then wget, then falls back to "unknown".
    """
    try:
        result = run_adb_shell(
            device_id,
            "curl -s --max-time 8 https://api.ipify.org 2>/dev/null",
        ).strip()
        if result and "." in result and len(result) <= 15:
            return result

        result = run_adb_shell(
            device_id,
            "wget -qO- --timeout=8 https://api.ipify.org 2>/dev/null",
        ).strip()
        if result and "." in result and len(result) <= 15:
            return result
    except Exception as exc:
        logger.debug(f"Could not fetch external IP: {exc}")

    return "unknown"


__all__ = ["get_device_external_ip"]
