"""The base of a platform's app on a connected phone, shared by every host that drives one.

A bridge and the CLI prepare the phone of a run the same way: one connection (`ConnectionService`),
the app lifecycle (`AppService`), what the platform mounts on the device, then the device facade over
it. This module never configures the process it is imported in (stdio, log handlers): a bridge entry
sets up its own environment first.
"""

from __future__ import annotations

from typing import Optional


class PlatformDeviceBase:
    """
    Shared scaffolding for any host object that needs a device connection and
    an app lifecycle (Instagram, Threads, ...).

    Subclasses must set:
      - `PLATFORM`: key understood by `AppService` (e.g. "instagram").
      - `DEFAULT_PACKAGE`: default Android package for that platform.

    Subclasses MAY override `_after_connect()` to inject custom logic
    after the connection is up (e.g. wrapping the device in a proxy), and
    `_apply_selector_version_overrides()` when the platform's selector
    catalogs follow the installed version.
    """

    PLATFORM: str = ""
    DEFAULT_PACKAGE: str = ""

    def __init__(self, device_id: str, package_name: Optional[str] = None):
        from taktik.core.shared.device.connection import ConnectionService

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
        from taktik.core.shared.device.app_manager import AppService

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
        """Hook: match the platform's selector catalogs to the installed app version.

        A no-op here; a platform whose catalogs carry version overrides applies them (the
        Instagram device base does, from its installed version)."""
        return None

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


__all__ = ["PlatformDeviceBase"]
