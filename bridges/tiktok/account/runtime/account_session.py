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

        if not self._validate_android_user(device):
            return None

        self._launch_tiktok()
        return device

    def _validate_android_user(self, device) -> bool:
        """Refuse to operate in a different Android profile than requested."""
        if self.android_user_id in (None, ""):
            self.android_user_id = None
            return True
        try:
            requested = int(self.android_user_id)
            if requested < 0:
                raise ValueError
        except (TypeError, ValueError):
            send_error("androidUserId must be a non-negative integer")
            return False

        try:
            response = device.shell("am get-current-user")
            output = getattr(response, "output", response)
            current = int(str(output).strip())
        except Exception as exc:  # noqa: BLE001
            send_error(f"Could not verify androidUserId {requested}: {exc}")
            return False
        if current != requested:
            send_error(
                f"androidUserId {requested} is not the active Android user (current: {current})"
            )
            return False
        self.android_user_id = requested
        return True

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
        send_status("initializing", "Restarting TikTok...")
        app_service = AppService(
            self._connection,
            platform="tiktok",
            package_override=self.package_name,
        )
        if self.workflow_type in {"switch_account", "list_accounts"} and app_service.is_running():
            send_status("initializing", "TikTok already open — using the current account state")
        else:
            # Login/logout/register retain their known clean starting state.
            app_service.restart()
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
