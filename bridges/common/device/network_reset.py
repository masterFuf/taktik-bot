"""Network reset strategies for bridge device runtimes."""

import time

from loguru import logger

from taktik.core.shared.device.adb import run_adb_shell


def reset_mobile_data(device_id: str, wait_seconds: float = 5.0) -> bool:
    """Toggle mobile data off/on to force a new carrier IP."""
    try:
        logger.info(f"Resetting mobile data on {device_id} to get a new IP")

        result = run_adb_shell(device_id, "svc data disable")
        if "error" in str(result).lower() or "permission" in str(result).lower():
            logger.warning(f"Failed to disable data: {result}")
            return False

        logger.debug(f"Mobile data disabled, waiting {wait_seconds}s")
        time.sleep(wait_seconds)

        result = run_adb_shell(device_id, "svc data enable")
        if "error" in str(result).lower() or "permission" in str(result).lower():
            logger.warning(f"Failed to enable data: {result}")
            return False

        time.sleep(3)
        logger.info("Mobile data reset complete, a new IP should be assigned")
        return True
    except Exception as exc:
        logger.error(f"Network reset failed: {exc}")
        return False


def reset_airplane_mode(device_id: str, wait_seconds: float = 5.0) -> bool:
    """Toggle airplane mode on/off to force a full network reconnect."""
    try:
        logger.info(f"Toggling airplane mode on {device_id} to get a new IP")

        result = run_adb_shell(device_id, "cmd connectivity airplane-mode enable")
        if "error" in str(result).lower():
            logger.warning(f"Failed to enable airplane mode: {result}")
            return False

        logger.debug(f"Airplane mode ON, waiting {wait_seconds}s")
        time.sleep(wait_seconds)

        result = run_adb_shell(device_id, "cmd connectivity airplane-mode disable")
        if "error" in str(result).lower():
            logger.warning(f"Failed to disable airplane mode: {result}")
            return False

        time.sleep(5)
        logger.info("Airplane mode reset complete, a new IP should be assigned")
        return True
    except Exception as exc:
        logger.error(f"Airplane mode reset failed: {exc}")
        return False


__all__ = ["reset_airplane_mode", "reset_mobile_data"]
