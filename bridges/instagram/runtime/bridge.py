"""Instagram-specific bridge base and clone-aware device proxy."""

from bridges.common.runtime.bridge_base import PlatformBridgeBase
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy as _CloneAwareDeviceProxy


class InstagramBridgeBase(PlatformBridgeBase):
    """Instagram-specific bridge base.

    Extends `PlatformBridgeBase` with clone package registration, transparent
    device proxying for clone resourceId rewriting, and the historical
    `restart_instagram()` alias.
    """

    PLATFORM = "instagram"
    DEFAULT_PACKAGE = "com.instagram.android"

    def _after_connect(self) -> None:
        """Register clone package globally and wrap device proxy everywhere."""
        if not (self.package_name and self.package_name != self.DEFAULT_PACKAGE):
            return

        from taktik.core.clone import set_active_package

        set_active_package(self.package_name)

        raw_device = self._connection.device
        if isinstance(raw_device, _CloneAwareDeviceProxy):
            proxy = raw_device
        else:
            proxy = _CloneAwareDeviceProxy(raw_device, self.package_name)

        self.device = proxy
        if self.device_manager is not None:
            self.device_manager.device = proxy
        try:
            self._connection._device = proxy
        except AttributeError:
            pass

    def rid(self, resource_id: str) -> str:
        """Resolve a resource-id for the active package."""
        if self.package_name and self.package_name != self.DEFAULT_PACKAGE:
            return resource_id.replace(self.DEFAULT_PACKAGE, self.package_name)
        return resource_id

    def restart_instagram(self):
        """Backward-compatible alias for `restart()`."""
        self.restart()


__all__ = ["InstagramBridgeBase", "_CloneAwareDeviceProxy"]
