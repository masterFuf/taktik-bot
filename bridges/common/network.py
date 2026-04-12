"""
Network Utilities — Reset mobile data / airplane mode to get a new IP.

Uses ADB shell commands via adbutils (preferred) or subprocess fallback.
Works on non-rooted devices.
"""

import time
from loguru import logger

from taktik.core.shared.input.taktik_keyboard import run_adb_shell


def get_device_external_ip(device_id: str) -> str:
    """
    Fetch the external/carrier IP of the device via ADB shell.
    Tries curl first, then wget, then falls back to "unknown".
    """
    try:
        # Try curl (present on most Android 7+)
        result = run_adb_shell(device_id, "curl -s --max-time 8 https://api.ipify.org 2>/dev/null").strip()
        if result and '.' in result and len(result) <= 15:
            return result
        # Try wget
        result = run_adb_shell(device_id, "wget -qO- --timeout=8 https://api.ipify.org 2>/dev/null").strip()
        if result and '.' in result and len(result) <= 15:
            return result
    except Exception as e:
        logger.debug(f"Could not fetch external IP: {e}")
    return "unknown"


def reset_mobile_data(device_id: str, wait_seconds: float = 5.0) -> bool:
    """
    Toggle mobile data off/on to force the carrier to assign a new IP.
    Works on non-rooted devices via ADB.

    Args:
        device_id: ADB device serial
        wait_seconds: Time to wait between disable and enable (default 5s)

    Returns:
        True if the reset sequence completed without errors
    """
    try:
        logger.info(f"📡 Resetting mobile data on {device_id} to get new IP...")

        # Disable mobile data
        result = run_adb_shell(device_id, "svc data disable")
        if "error" in str(result).lower() or "permission" in str(result).lower():
            logger.warning(f"Failed to disable data: {result}")
            return False

        logger.debug(f"Mobile data disabled, waiting {wait_seconds}s...")
        time.sleep(wait_seconds)

        # Re-enable mobile data
        result = run_adb_shell(device_id, "svc data enable")
        if "error" in str(result).lower() or "permission" in str(result).lower():
            logger.warning(f"Failed to enable data: {result}")
            return False

        # Wait for connection to re-establish
        time.sleep(3)
        logger.info("✅ Mobile data reset complete — new IP should be assigned")
        return True

    except Exception as e:
        logger.error(f"❌ Network reset failed: {e}")
        return False


def reset_airplane_mode(device_id: str, wait_seconds: float = 5.0) -> bool:
    """
    Toggle airplane mode on/off to force a full network reconnect (new IP).
    Works on non-rooted devices via ADB.

    Args:
        device_id: ADB device serial
        wait_seconds: Time to wait in airplane mode (default 5s)

    Returns:
        True if the reset sequence completed without errors
    """
    try:
        logger.info(f"✈️ Toggling airplane mode on {device_id} to get new IP...")

        # Enable airplane mode
        result = run_adb_shell(device_id, "cmd connectivity airplane-mode enable")
        if "error" in str(result).lower():
            logger.warning(f"Failed to enable airplane mode: {result}")
            return False

        logger.debug(f"Airplane mode ON, waiting {wait_seconds}s...")
        time.sleep(wait_seconds)

        # Disable airplane mode
        result = run_adb_shell(device_id, "cmd connectivity airplane-mode disable")
        if "error" in str(result).lower():
            logger.warning(f"Failed to disable airplane mode: {result}")
            return False

        # Wait for full reconnect (WiFi + data)
        time.sleep(5)
        logger.info("✅ Airplane mode reset complete — new IP should be assigned")
        return True

    except Exception as e:
        logger.error(f"❌ Airplane mode reset failed: {e}")
        return False


def perform_network_reset(device_id: str, method: str = "data", ipc=None) -> bool:
    """
    High-level network reset dispatcher.

    Args:
        device_id: ADB device serial
        method: "data" (mobile data toggle) or "airplane" (airplane mode toggle)
        ipc: Optional IPC instance to send status messages

    Returns:
        True if reset was successful
    """
    if ipc:
        ipc.status("resetting_network", f"Getting current IP...")

    old_ip = get_device_external_ip(device_id)
    logger.info(f"📡 Current IP: {old_ip}")

    if ipc:
        ipc.status("resetting_network", f"Resetting network ({method}) for new IP...")

    if method == "airplane":
        success = reset_airplane_mode(device_id)
    else:
        success = reset_mobile_data(device_id)

    new_ip = "unknown"
    if success:
        new_ip = get_device_external_ip(device_id)
        logger.info(f"📡 New IP: {new_ip}")

    if ipc:
        if success:
            ipc.log("info", f"📡 Network reset done — {old_ip} → {new_ip}")
        else:
            ipc.log("warning", "⚠️ Network reset may have failed — continuing anyway")

        ipc.send("network_reset_complete", **{
            "old_ip": old_ip,
            "new_ip": new_ip,
            "method": method,
            "success": success,
        })

    return success
