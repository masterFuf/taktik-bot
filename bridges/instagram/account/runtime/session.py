"""Session lifecycle for the Instagram account bridge."""

from __future__ import annotations

import time

from bridges.common.device.app_manager import AppService
from bridges.common.device.connection import ConnectionService
from bridges.instagram.runtime.ipc import send_error, send_status


class AccountSessionLifecycleMixin:
    """Prepare DB, device connection and Instagram launch before account workflows."""

    def _prepare_runtime_session(self):
        try:
            from taktik.core.database import configure_db_service

            configure_db_service()
        except Exception as e:
            send_error(f"Database setup failed: {e}")
            return None

        send_status("connecting", f"Connecting to device {self.device_id}...")
        self._connection = ConnectionService(self.device_id)
        if not self._connection.connect():
            send_error(f"Failed to connect to device {self.device_id}")
            return None

        device = self._connection.device
        if not device:
            send_error("Device object unavailable after connection")
            return None

        app_service = AppService(
            self._connection,
            platform="instagram",
            package_override=self.package_name,
        )
        # Account switch / list act on Instagram's current account-picker (or home) state. A cold
        # force-restart there is wasteful — it just lands us back on the same picker. So when IG is
        # ALREADY in the foreground, keep the current screen (the workflow detects the picker or
        # navigates); only fall back to a clean restart when it isn't showing. Every other account
        # flow (login/register/logout/change_language) keeps the clean restart for a known state.
        if self.workflow_type in ("switch_account", "list_accounts", "list_saved_accounts") and app_service.is_running():
            send_status("initializing", "Instagram already open — using the current screen")
            time.sleep(1)
        else:
            send_status("initializing", "Restarting Instagram...")
            app_service.restart()
            time.sleep(2)

        return device
