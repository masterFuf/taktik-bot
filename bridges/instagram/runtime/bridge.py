"""Instagram-specific bridge base and clone-aware device proxy."""

from bridges.common.runtime.platform_bridge import PlatformBridgeBase
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
        """Wrap the device in the clone-aware, package-agnostic proxy — ALWAYS.

        Mounted unconditionally now, not only for clones. The proxy turns every exact
        ``resourceId=`` into a package-agnostic ``resourceIdMatches``, and that is what lets
        the STOCK app be driven on Instagram 442: 442 exposes its Jetpack Compose content ids
        with NO package prefix (`activity_feed_newsfeed_story_row`, not
        `com.instagram.android:id/…`), so an exact match found nothing. The proxy used to be
        clone-only, so the stock app never got that treatment — which is why a phone that
        auto-updated to 442 stopped finding its rows.
        """
        from taktik.core.clone import set_active_package

        # Register the active package so the (still prefix-based) xpath/rid path resolves a
        # clone. On stock this is the official package, a no-op.
        if self.package_name and self.package_name != self.DEFAULT_PACKAGE:
            set_active_package(self.package_name)

        raw_device = self._connection.device
        if isinstance(raw_device, _CloneAwareDeviceProxy):
            proxy = raw_device
        else:
            proxy = _CloneAwareDeviceProxy(raw_device, self.package_name or self.DEFAULT_PACKAGE)

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
