"""The phone a CLI run drives, connected only when a launcher asks for it.

`taktik workflows run` chooses the phone (its serial) before it runs anything, but does not connect
to it: the launcher reads and validates its payload first, then calls the `connect` the CLI host
gave it, and only that call connects. A payload the reader refuses (a setting out of its bounds, a
scraping with no source) ends before anything reaches the phone, as from the desktop bridges.

In Symfony terms: a lazy service. The CLI hands every host the same `CliPhone`; the first host
method that needs the phone calls `connect()`, which connects once, and every later call gets the
same connection. A menu that already connected its phone hands its manager in: `connect()` then
returns it as it is.
"""
from __future__ import annotations

from typing import Any


class PhoneNotConnectedError(RuntimeError):
    """The CLI could not connect to the phone a launcher asked for."""


class CliPhone:
    """One phone of a CLI run: its serial, and its `DeviceManager`, connected on first use.

    `device_manager` is a `DeviceManager` not yet connected (`taktik workflows run`), or one a menu
    connected already. It counts as connected once it holds a `device`.
    """

    def __init__(self, device_manager: Any, device_id: str):
        self.device_manager = device_manager
        self.device_id = device_id

    @property
    def connected(self) -> bool:
        return getattr(self.device_manager, "device", None) is not None

    def connect(self) -> Any:
        """The connected `DeviceManager`: the first call connects it; raises when it does not connect."""
        if not self.connected:
            if not self.device_manager.connect(self.device_id) or not self.connected:
                raise PhoneNotConnectedError(f"Cannot connect to {self.device_id}.")
        return self.device_manager


__all__ = ["CliPhone", "PhoneNotConnectedError"]
