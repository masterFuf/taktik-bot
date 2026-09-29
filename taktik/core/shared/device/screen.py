"""Screen information helpers for bridge device connections."""

from typing import Any, Tuple

from loguru import logger


DEFAULT_SCREEN_SIZE = (1080, 2340)


def read_screen_size(device: Any, default: Tuple[int, int] = DEFAULT_SCREEN_SIZE) -> Tuple[int, int]:
    """Read display dimensions from a uiautomator2 device object."""
    try:
        screen_info = device.info
        width = int(screen_info.get("displayWidth", default[0]))
        height = int(screen_info.get("displayHeight", default[1]))
        return width, height
    except Exception as exc:
        logger.warning(f"Could not read screen dimensions: {exc}")
        return default


__all__ = ["DEFAULT_SCREEN_SIZE", "read_screen_size"]
