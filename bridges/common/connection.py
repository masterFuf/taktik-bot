"""
ConnectionService — single source of truth for device connections.

Wraps DeviceManager to provide a clean, reusable interface for all bridges.
Handles: connect, disconnect, screen info, ATX health checks.

Usage:
    from bridges.common.connection import ConnectionService

    conn = ConnectionService("DEVICE_SERIAL")
    if not conn.connect():
        sys.exit(1)

    device = conn.device              # uiautomator2 device object
    dm = conn.device_manager          # raw DeviceManager if needed
    w, h = conn.screen_size           # (1080, 2340)
"""

import time
from typing import Optional, Tuple
from loguru import logger


class ConnectionService:
    """
    Manages the connection to a single Android device.

    Provides a single DeviceManager instance that all other services
    (AppService, KeyboardService, etc.) can share — eliminating the
    "double DeviceManager" bug that existed before.
    """

    def __init__(self, device_id: str):
        self.device_id = device_id
        self._device_manager = None
        self._device = None
        self._screen_width: int = 1080
        self._screen_height: int = 2340
        self._connected: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """
        Connect to the device via DeviceManager.

        Returns True if connection succeeds.
        Safe to call multiple times — will skip if already connected.
        """
        if self._connected and self._device is not None:
            logger.debug(f"Already connected to {self.device_id}")
            return True

        logger.info(f"Connecting to device: {self.device_id}")
        try:
            from taktik.core.social_media.instagram.actions.core.device import DeviceManager

            self._device_manager = DeviceManager(device_id=self.device_id)

            if not self._device_manager.connect():
                logger.error(f"DeviceManager.connect() failed for {self.device_id}")
                return False

            self._device = self._device_manager.device
            if self._device is None:
                logger.error("Device is None after connect()")
                return False

            # Cache screen dimensions
            try:
                screen_info = self._device.info
                self._screen_width = screen_info.get('displayWidth', 1080)
                self._screen_height = screen_info.get('displayHeight', 2340)
            except Exception as e:
                logger.warning(f"Could not read screen dimensions: {e}")

            self._connected = True
            logger.info(f"Connected to {self.device_id} ({self._screen_width}x{self._screen_height})")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._device_manager:
            try:
                self._device_manager.disconnect()
            except Exception:
                pass
        self._connected = False
        self._device = None
        logger.info(f"Disconnected from {self.device_id}")

    def check_atx_health(self, repair: bool = True, max_retries: int = 3) -> dict:
        """
        Check ATX (uiautomator2) agent health on the connected device.

        Args:
            repair: If True, attempt automatic repair when unhealthy.
            max_retries: Number of repair attempts.

        Returns:
            Dict with keys: atx_healthy (bool), error (str|None), repaired (bool).
        """
        if not self._device_manager:
            return {"atx_healthy": False, "error": "Not connected", "repaired": False}

        try:
            status = self._device_manager.get_atx_status()
            if status.get("atx_healthy"):
                return {"atx_healthy": True, "error": None, "repaired": False}

            error_detail = status.get("error", "Unknown ATX error")
            logger.warning(f"ATX agent unhealthy: {error_detail}")

            if repair:
                logger.info("Attempting ATX repair...")
                if self._device_manager._verify_and_repair_atx(max_retries=max_retries):
                    logger.info("ATX agent repaired successfully")
                    return {"atx_healthy": True, "error": None, "repaired": True}
                else:
                    logger.warning("ATX repair failed")

            return {"atx_healthy": False, "error": error_detail, "repaired": False}

        except Exception as e:
            logger.warning(f"ATX health check error: {e}")
            return {"atx_healthy": False, "error": str(e), "repaired": False}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def device(self):
        """The uiautomator2 device object. None if not connected."""
        return self._device

    @property
    def device_manager(self):
        """The underlying DeviceManager. None if not connected."""
        return self._device_manager

    @property
    def screen_size(self) -> Tuple[int, int]:
        """Screen dimensions as (width, height)."""
        return (self._screen_width, self._screen_height)

    @property
    def screen_width(self) -> int:
        return self._screen_width

    @property
    def screen_height(self) -> int:
        return self._screen_height

    @property
    def is_connected(self) -> bool:
        return self._connected and self._device is not None
