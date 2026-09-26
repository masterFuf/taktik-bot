"""Device/app preparation for the TikTok account bridge."""

from bridges.common.device.app_manager import AppService
from bridges.common.device.connection import ConnectionService
from bridges.tiktok.runtime.ipc import send_error, send_status


class TikTokAccountSessionMixin:
    """Prepare shared runtime dependencies before dispatching an account workflow."""

    def _prepare_device(self):
        if not self._setup_database():
            return None

        device = self._connect_device()
        if device is None:
            return None

        # The clean restart itself is `run_tiktok_account`'s, on this app service.
        self._app = AppService(
            self._connection,
            platform="tiktok",
            package_override=self.package_name,
        )
        return device

    def _setup_database(self) -> bool:
        try:
            from taktik.core.database import configure_db_service

            configure_db_service()
            return True
        except Exception as e:
            send_error(f"Database setup failed: {e}")
            return False

    def _connect_device(self):
        send_status("connecting", f"Connecting to device {self.device_id}...")
        self._connection = ConnectionService(self.device_id)
        if not self._connection.connect():
            send_error(f"Failed to connect to device {self.device_id}")
            return None

        device = self._connection.device
        if not device:
            send_error("Device object unavailable after connection")
            return None
        return device
