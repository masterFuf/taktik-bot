"""Standalone app control helpers for bridge device services."""

from loguru import logger

from bridges.common.device.apps import get_app_config, packages_for_platform
from taktik.core.shared.device.adb import run_adb_shell_process


def force_stop_app(device_id: str, platform: str) -> bool:
    """
    Force-stop a platform app on the given device using ADB.

    Does not require an active uiautomator2 connection, so it is safe to call
    from cleanup/finally paths after a workflow ends.
    """
    config = get_app_config(platform)
    if not config:
        logger.warning(f"[AppService] Unknown platform '{platform}' for force-stop")
        return False

    success = False
    for package_name in packages_for_platform(platform):
        try:
            result = run_adb_shell_process(
                device_id,
                ["am", "force-stop", package_name],
                text=False,
                timeout=5,
            )
            if result.returncode == 0:
                logger.info(f"[AppService] Closed {platform} ({package_name}) on {device_id}")
                success = True
                break
        except Exception as exc:
            logger.warning(f"[AppService] Could not force-stop {platform} ({package_name}): {exc}")

    if not success:
        logger.warning(f"[AppService] force_stop_app failed for {platform} on {device_id}")
    return success
