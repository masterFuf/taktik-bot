"""Device/app preparation for the TikTok account bridge."""

import time

from bridges.common.device.app_manager import AppService
from bridges.common.device.connection import ConnectionService
from bridges.tiktok.runtime.ipc import send_error, send_log, send_status


class TikTokAccountSessionMixin:
    """Prepare shared runtime dependencies before dispatching an account workflow."""

    def _prepare_device(self):
        if not self._setup_database():
            return None

        device = self._connect_device()
        if device is None:
            return None

        self._launch_tiktok()
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

    def _launch_tiktok(self) -> None:
        send_status("initializing", "Launching TikTok...")
        app_service = AppService(
            self._connection,
            platform="tiktok",
            package_override=self.package_name,
        )
        app_service.launch()
        self._patch_clone_selectors(app_service.package)
        time.sleep(2)

    def _patch_clone_selectors(self, resolved_package: str) -> None:
        if resolved_package == "com.zhiliaoapp.musically":
            return

        try:
            from taktik.core.clone import patch_selectors_for_package, set_active_package

            set_active_package(resolved_package)
            patched = patch_selectors_for_package("tiktok", resolved_package)
            send_log("info", f"🧬 Package override: patched {patched} TikTok selector(s) for {resolved_package}")
        except Exception as e:
            send_log("warning", f"⚠️ Clone selector patching failed (non-fatal): {e}")
