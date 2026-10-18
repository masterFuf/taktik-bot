"""A recording stand-in for the CLI's `DeviceManager`, shared by the tests that watch when the CLI
connects its phone.

`taktik workflows run` chooses a phone without connecting it (`taktik/cli/hosts/phone.py`): a
launcher connects it once it has read its payload. A test hands the CLI this class (as
`DeviceManager`, or inside a `CliPhone`) and reads `calls` to see whether, and when, it connected.
"""
from __future__ import annotations

from typing import Any, Optional


def recording_device_manager(calls: list, device_id: str, connected: Optional[Any] = None) -> type:
    """A `DeviceManager` class: adb lists `device_id`; `connect(serial)` appends `cli_connect <serial>`,
    then holds `connected`'s device and serves its app calls (`connected` None: a bare device)."""

    class RecordingDeviceManager:
        def __init__(self, *_args, **_kwargs):
            self.device = None

        @staticmethod
        def list_devices():
            return [{"id": device_id, "status": "device"}]

        def connect(self, serial=None, verify_atx=True):
            calls.append(f"cli_connect {serial}")
            self.device = connected.device if connected is not None else object()
            return True

        def __getattr__(self, name):
            if connected is None:
                raise AttributeError(name)
            return getattr(connected, name)

    return RecordingDeviceManager


__all__ = ["recording_device_manager"]
