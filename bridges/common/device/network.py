"""Network reset facade for bridge device runtimes."""

from loguru import logger

from bridges.common.device.network_probe import get_device_external_ip
from bridges.common.device.network_reset import (
    reset_airplane_mode,
    reset_mobile_data,
)


def perform_network_reset(device_id: str, method: str = "data", ipc=None) -> bool:
    """
    High-level network reset dispatcher.

    Args:
        device_id: ADB device serial.
        method: "data" (mobile data toggle) or "airplane" (airplane mode toggle).
        ipc: Optional IPC instance to send status messages.

    Returns:
        True if reset was successful.
    """
    if ipc:
        ipc.status("resetting_network", "Getting current IP...")

    old_ip = get_device_external_ip(device_id)
    logger.info(f"Current IP: {old_ip}")

    if ipc:
        ipc.status("resetting_network", f"Resetting network ({method}) for new IP...")

    if method == "airplane":
        success = reset_airplane_mode(device_id)
    else:
        success = reset_mobile_data(device_id)

    new_ip = "unknown"
    if success:
        new_ip = get_device_external_ip(device_id)
        logger.info(f"New IP: {new_ip}")

    if ipc:
        if success:
            ipc.log("info", f"Network reset done: {old_ip} -> {new_ip}")
        else:
            ipc.log("warning", "Network reset may have failed, continuing anyway")

        ipc.send(
            "network_reset_complete",
            old_ip=old_ip,
            new_ip=new_ip,
            method=method,
            success=success,
        )

    return success


__all__ = [
    "get_device_external_ip",
    "perform_network_reset",
    "reset_airplane_mode",
    "reset_mobile_data",
]
