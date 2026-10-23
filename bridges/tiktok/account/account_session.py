"""Device/app preparation for the TikTok account bridge."""

from taktik.core.shared.device.app_manager import AppService
from bridges.common.run_setup import connect_run_device


class TikTokAccountSessionMixin:
    """Prepare shared runtime dependencies before dispatching an account workflow."""

    def _prepare_device(self):
        self._connection = connect_run_device(self.device_id)
        if self._connection is None:
            return None

        # The clean restart itself is `run_tiktok_account`'s, on this app service.
        self._app = AppService(
            self._connection,
            platform="tiktok",
            package_override=self.package_name,
        )
        return self._connection.device
