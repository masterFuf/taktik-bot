"""The Instagram device a run drives, prepared the same way by every host.

The desktop bridges, the CLI and the Cartography Lab connect Instagram through this base: the
clone-aware proxy on every connection, the device facade over it, the selector overrides of the
installed version, and the clean restart through `AppService`. A host already connected to the
phone hands it its device (`taktik.core.shared.device.connected_device.on_connected_device`).
"""

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.platform_device import PlatformDeviceBase


class InstagramDeviceBase(PlatformDeviceBase):
    """Instagram on a connected phone.

    Extends `PlatformDeviceBase` with clone package registration, transparent
    device proxying for clone resourceId rewriting, the selector overrides of
    the installed version, and the historical `restart_instagram()` alias.
    """

    PLATFORM = "instagram"
    DEFAULT_PACKAGE = "com.instagram.android"

    def _after_connect(self) -> None:
        """Wrap the device in the clone-aware, package-agnostic proxy — ALWAYS.

        Mounted unconditionally now, not only for clones. The proxy turns every exact Instagram
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
        if isinstance(raw_device, CloneAwareDeviceProxy):
            proxy = raw_device
        else:
            proxy = CloneAwareDeviceProxy(raw_device, self.package_name or self.DEFAULT_PACKAGE)

        self.device = proxy
        if self.device_manager is not None:
            self.device_manager.device = proxy
        try:
            self._connection._device = proxy
        except AttributeError:
            pass

    def _apply_selector_version_overrides(self) -> None:
        """Patch the selector catalogs for the app version actually installed.

        The version-override framework (`taktik.core.compat.selectors`) existed and
        worked — but only the Cartography Lab's workflow-test bench ever called it.
        Production bridges ran on the baseline selectors whatever the phone had, so
        an auto-updated Instagram (v442 rebuilt the DM inbox in Compose, dropping
        every row resource-id) failed with "No threads found" while the Lab, on the
        same phone, would have patched itself and passed. A compat table only the
        test bench reads is a fix that never ships.

        Best-effort by design: no override file, an undetectable version, or a
        version equal to the baseline are all no-ops, and a failure here must never
        prevent a run from starting — the baseline selectors are still the right
        answer for the validated version.
        """
        try:
            version = self._app.get_installed_version() if self._app else None
            if not version:
                return
            from taktik.core.compat.selectors.setup import apply_version_overrides

            apply_version_overrides(self.PLATFORM, version)
        except Exception as exc:  # noqa: BLE001 — overrides are an upgrade, never a gate
            import logging

            logging.getLogger(__name__).warning(
                "Selector version overrides skipped: %s", exc
            )

    def rid(self, resource_id: str) -> str:
        """Resolve a resource-id for the active package."""
        if self.package_name and self.package_name != self.DEFAULT_PACKAGE:
            return resource_id.replace(self.DEFAULT_PACKAGE, self.package_name)
        return resource_id

    def restart_instagram(self):
        """Backward-compatible alias for `restart()`."""
        self.restart()


__all__ = ["InstagramDeviceBase"]
