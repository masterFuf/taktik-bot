"""ATX health helpers for bridge device connections."""

from loguru import logger


def check_atx_health(device_manager, repair: bool = True, max_retries: int = 3) -> dict:
    """Check and optionally repair the ATX agent on a connected device."""
    if not device_manager:
        return {"atx_healthy": False, "error": "Not connected", "repaired": False}

    try:
        status = device_manager.get_atx_status()
        if status.get("atx_healthy"):
            return {"atx_healthy": True, "error": None, "repaired": False}

        error_detail = status.get("error", "Unknown ATX error")
        logger.warning(f"ATX agent unhealthy: {error_detail}")

        if repair:
            logger.info("Attempting ATX repair...")
            if device_manager._verify_and_repair_atx(max_retries=max_retries):
                logger.info("ATX agent repaired successfully")
                return {"atx_healthy": True, "error": None, "repaired": True}
            logger.warning("ATX repair failed")

        return {"atx_healthy": False, "error": error_detail, "repaired": False}

    except Exception as exc:
        logger.warning(f"ATX health check error: {exc}")
        return {"atx_healthy": False, "error": str(exc), "repaired": False}
