"""Platform-agnostic bridge base class for connected mobile-app runtimes."""

from __future__ import annotations

from typing import Optional

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()


class PlatformBridgeBase:
    """
    Shared scaffolding for any bridge that needs a device connection and
    an app lifecycle (Instagram, TikTok, Threads, YouTube, ...).

    Subclasses must set:
      - `PLATFORM`: key understood by `AppService` (e.g. "instagram").
      - `DEFAULT_PACKAGE`: default Android package for that platform.

    Subclasses MAY override `_after_connect()` to inject custom logic
    after the connection is up (e.g. wrapping the device in a proxy).
    """

    PLATFORM: str = ""
    DEFAULT_PACKAGE: str = ""

    def __init__(self, device_id: str, package_name: Optional[str] = None):
        from bridges.common.device.connection import ConnectionService

        self.device_id = device_id
        self.package_name = package_name or self.DEFAULT_PACKAGE
        self._connection = ConnectionService(device_id)
        self._app = None
        # Backward-compatible aliases populated by `connect()`.
        self.device_manager = None
        self.device = None
        self.screen_width = 1080
        self.screen_height = 2340

    def connect(self) -> bool:
        """Open the device connection and bootstrap the AppService."""
        from bridges.common.device.app_manager import AppService

        if not self._connection.connect():
            return False
        self.device_manager = self._connection.device_manager
        self.device = self._connection.device
        self.screen_width, self.screen_height = self._connection.screen_size

        # Pass `package_override` only when it differs from the platform default,
        # so AppService can keep auto-detection for clone/multi-package platforms.
        override = (
            self.package_name
            if self.package_name and self.package_name != self.DEFAULT_PACKAGE
            else None
        )
        self._app = AppService(
            self._connection,
            platform=self.PLATFORM,
            package_override=override,
        )

        self._after_connect()
        # Facade LAST, on purpose: `_after_connect` may swap the device for a proxy (the
        # Instagram clone rewriter does), and the facade has to wrap whatever ends up in play
        # or that proxy drops out of the chain.
        self.device = self._wrap_in_facade(self.device)
        self._apply_selector_version_overrides()
        return True

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
        prevent a bridge from running — the baseline selectors are still the right
        answer for the validated version.
        """
        if self.PLATFORM not in ("instagram", "tiktok"):
            return
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

    def _wrap_in_facade(self, device):
        """Expose a DeviceFacade rather than the raw uiautomator2 device.

        The facade is a superset: `__getattr__` forwards every attribute and `__call__`
        forwards the selector idiom, so the 50 call sites written as `self.device(resourceId=…)`
        keep working untouched. What the bridges gain is everything the workflows already had —
        humanised taps and gestures, `xpath`, XML dumps — which was unreachable from here for no
        reason other than the facade not being callable.
        """
        from taktik.core.shared.device.facade import BaseDeviceFacade

        if device is None or isinstance(device, BaseDeviceFacade):
            return device
        return BaseDeviceFacade(device, module_name=f"{self.PLATFORM or 'platform'}-bridge-device")

    def _after_connect(self) -> None:
        """Hook for subclasses to inject post-connection logic."""
        return None

    def restart(self) -> None:
        """Restart the app for a clean initial state via AppService."""
        if self._app is None:
            raise RuntimeError(
                f"{type(self).__name__}.restart() called before connect()"
            )
        self._app.restart()

    def stop(self) -> bool:
        """Force-stop the app — the counterpart of `restart()` for a finished run.

        Best-effort: a bridge that has finished its work should leave the phone on a
        clean screen, but failing to close the app must never turn a successful run
        into an error. Returns False when not connected or when the stop failed.
        """
        if self._app is None:
            return False
        try:
            return bool(self._app.stop())
        except Exception:  # noqa: BLE001 — closing the app is never worth failing a run
            return False


__all__ = ["PlatformBridgeBase"]
