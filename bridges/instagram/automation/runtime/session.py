"""Device, database and app lifecycle for Instagram desktop automation runtime."""

from __future__ import annotations

from bridges.common.device.app_manager import AppService
from bridges.common.device.connection import ConnectionService
from bridges.instagram.runtime.ipc import _ipc, logger, send_error, send_status


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

    def reset_network_if_enabled(self, ipc) -> bool:
        """Run the optional network reset before launching Instagram.

        Returns False when the user asked for a fresh IP and the rotation provably did not happen —
        the run must NOT start, because the account would then act from the IP the previous account
        just used. An IP that simply could not be read is reported but does not block: absence of
        proof is not proof of failure, and blocking on it would ground every phone whose shell has
        no HTTP tool.
        """
        from bridges.common.device.network import enforce_pre_session_ip_rotation

        return enforce_pre_session_ip_rotation(
            {"networkReset": {"enabled": self.network_reset_enabled, "method": self.network_reset_method}},
            self.device_id,
            ipc=ipc,
            label="Session",
        )

    def launch_instagram(self) -> bool:
        """Restart Instagram on the connected device for a clean, consistent initial state.

        The sequence is the core's (`start_instagram_session`), shared with the CLI; the bridge
        brings its app service, its uiautomator2 check and its stdout.
        """
        from taktik.core.social_media.instagram.workflows.core.startup import start_instagram_session

        return start_instagram_session(
            self.app_service,
            notifier=_ipc,
            health_check=lambda: self.connection.check_atx_health(repair=True, max_retries=3),
        )

    def stop_app(self) -> None:
        """Best-effort Instagram app stop at session end."""
        if not self.app_service:
            return

        try:
            self.app_service.stop()
        except Exception:
            pass
