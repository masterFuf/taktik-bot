"""Session lifecycle for the Instagram account bridge."""

from __future__ import annotations

from taktik.core.shared.device.app_manager import AppService
from bridges.common.run_setup import connect_run_device


class AccountSessionLifecycleMixin:
    """Prepare DB and device connection; the launcher decides how Instagram starts."""

    def _prepare_runtime_session(self):
        self._connection = connect_run_device(self.device_id)
        if self._connection is None:
            return None

        # Restart or keep the current screen: `run_instagram_account` chooses per flow.
        self._app = AppService(
            self._connection,
            platform="instagram",
            package_override=self.package_name,
        )
        return self._connection.device
