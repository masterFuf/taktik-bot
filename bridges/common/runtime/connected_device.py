"""A bridge's base on a phone its host already connected.

A bridge normally opens its own connection (`ConnectionService`). The CLI has connected the phone
before it knows which run it starts, and the Cartography Lab session holds its phone for every
action: opening a second connection would cost a reconnection and could pick another phone. Both
hand the bridge's base the connected device instead, and the base prepares it exactly as it
prepares its own (clone-aware proxy, device facade, selector overrides of the installed version,
the `AppService` that restarts the app). The run then drives the same class as the desktop bridge.
"""

from __future__ import annotations

from typing import Any


class ConnectedDevice:
    """A host's connected phone, as the connection a bridge's base expects.

    `device_manager` is whatever holds the connected `device`: the CLI's `DeviceManager`, or the
    Lab session's device in a namespace.
    """

    def __init__(self, device_manager: Any, device_id: str):
        self.device_manager = device_manager
        self.device_id = device_id
        self._device = getattr(device_manager, "device", None)

    @property
    def device(self):
        return self._device

    @property
    def screen_size(self):
        from bridges.common.device.screen import read_screen_size

        return read_screen_size(self._device)

    def connect(self) -> bool:
        return self._device is not None


def on_connected_device(base, device_manager: Any, device_id: str):
    """Connect a bridge's base (`InstagramBridgeBase` and its bridges) on the phone the host already
    connected; raises when the host has no device."""
    base._connection = ConnectedDevice(device_manager, device_id)
    if not base.connect():
        raise RuntimeError(f"No connected device for {device_id}")
    return base


__all__ = ["ConnectedDevice", "on_connected_device"]
