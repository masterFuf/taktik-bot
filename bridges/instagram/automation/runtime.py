"""Device, database and app lifecycle for Instagram desktop automation."""

from __future__ import annotations

from bridges.common.device.app_manager import AppService
from bridges.common.device.connection import ConnectionService
from bridges.instagram.base import logger, send_error, send_log, send_status


class InstagramDesktopRuntime:
    """Own bridge-owned runtime resources for one Instagram desktop session."""

    def __init__(self, *, device_id: str | None, package_name: str | None, network_reset: dict):
        self.device_id = device_id
        self.package_name = package_name
        self.network_reset = network_reset
        self.network_reset_enabled = network_reset.get("enabled", False)
        self.network_reset_method = network_reset.get("method", "data")
        self.connection = ConnectionService(device_id) if device_id else None
        self.app_service = None
        self.device_manager = None

    def setup_database(self) -> bool:
        """Configure the local SQLite service for this bot process."""
        try:
            send_status("initializing", "Setting up database service...")

            from taktik.core.database import configure_db_service

            configure_db_service()
            send_status("license_valid", "Database service configured")
            return True

        except Exception as e:
            send_error(f"Database setup failed: {str(e)}", error_code="LICENSE_SETUP_FAILED")
            logger.exception("Database setup failed")
            return False

    def connect_device(self) -> bool:
        """Connect to the specified device using ConnectionService."""
        try:
            send_status("connecting", f"Connecting to device {self.device_id}...")

            if not self.connection:
                self.connection = ConnectionService(self.device_id)

            if not self.connection.connect():
                send_error(
                    f"Failed to connect to device {self.device_id}",
                    error_code="DEVICE_CONNECTION_FAILED",
                )
                return False

            self.device_manager = self.connection.device_manager
            self.app_service = AppService(
                self.connection,
                platform="instagram",
                package_override=self.package_name,
            )

            send_status("connected", f"Connected to {self.device_id}")
            return True

        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                send_error(
                    f"Device connection timed out: {error_msg}",
                    error_code="DEVICE_CONNECTION_TIMEOUT",
                )
            else:
                send_error(
                    f"Failed to connect to device: {error_msg}",
                    error_code="DEVICE_CONNECTION_FAILED",
                )
            logger.exception("Device connection failed")
            return False

    def reset_network_if_enabled(self, ipc) -> None:
        """Run optional network reset before launching Instagram."""
        if not self.network_reset_enabled:
            return

        from bridges.common.device.network import perform_network_reset

        perform_network_reset(self.device_id, method=self.network_reset_method, ipc=ipc)

    def launch_instagram(self) -> bool:
        """Launch Instagram on the connected device."""
        try:
            send_status("launching", "Launching Instagram...")

            atx_result = self.connection.check_atx_health(repair=True, max_retries=3)
            if not atx_result["atx_healthy"]:
                error_detail = atx_result.get("error", "Unknown")
                if atx_result.get("repaired"):
                    send_status("atx_repaired", "UIAutomator2 agent repaired successfully")
                else:
                    logger.warning(f"ATX repair failed: {error_detail} - continuing anyway")
                    send_log(
                        "warning",
                        f"ATX repair failed ({error_detail}) but continuing - workflow may still work",
                    )

            if not self.app_service.is_installed():
                send_error("Instagram is not installed on this device", error_code="INSTAGRAM_NOT_INSTALLED")
                return False

            if not self.app_service.launch():
                send_error("Failed to launch Instagram", error_code="INSTAGRAM_LAUNCH_FAILED")
                return False

            send_status("instagram_ready", "Instagram launched successfully")
            return True

        except Exception as e:
            error_msg = str(e)
            if "uiautomator" in error_msg.lower() or "atx" in error_msg.lower():
                send_error(f"UIAutomator2 connection failed: {error_msg}", error_code="ATX_AGENT_FAILED")
            else:
                send_error(f"Failed to launch Instagram: {error_msg}", error_code="INSTAGRAM_LAUNCH_FAILED")
            logger.exception("Instagram launch failed")
            return False

    def stop_app(self) -> None:
        """Best-effort Instagram app stop at session end."""
        if not self.app_service:
            return

        try:
            self.app_service.stop()
        except Exception:
            pass
