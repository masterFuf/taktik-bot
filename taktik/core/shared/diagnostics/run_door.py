"""The door of a run: a phone that cannot run does not start, whatever the host.

A scraping on a C57S (Android 14, 2026-10-30) ran a minute on the lock screen, and ended
`target_never_reached` where the motive was a locked phone. Each launcher of the core opens this door
once its host hands it the phone, before the app starts and before any gesture: the lock of the screen
first (`shared/device/screen.py`: a lock without code is lifted, a lock that stays refuses the run),
then the network (`shared/device/network_door.py`). The desktop bridges and the CLI cross the same
call, so both refuse a locked phone with the same motive, and catch the one class `RunRefused`.

An unreadable state never blocks a run: a phone whose dump does not say its lock keeps its run, as a
phone whose shell has no ping. In Symfony terms: the voters the core consults before the run.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from taktik.core.shared.device.network_door import open_network_door
from taktik.core.shared.device.screen import phone_locked_after_lift
from taktik.core.shared.diagnostics.run_halt import RunRefused


class PhoneLockedError(RunRefused):
    """The phone stays locked once its lock was asked to go (a code, on most phones): no run starts."""

    error_code = "PHONE_LOCKED"

    def __init__(self, device_id: str):
        super().__init__(device_id, f"the phone {device_id} stays locked (dumpsys window: isKeyguardShowing=true)")


def open_run_door(device_id: Optional[str]) -> Optional[dict]:
    """Refuse a phone that stays locked, then one with no network (`RunRefused`). Returns the network
    door's measure, which starts the network watch of the run."""
    if device_id:
        locked = phone_locked_after_lift(device_id)
        if locked:
            logger.warning(f"Run door: {device_id} stays locked, the run does not start")
            raise PhoneLockedError(device_id)
        if locked is None:
            logger.warning(f"Run door: the lock of {device_id} is unreadable, the run goes on")
    return open_network_door(device_id)


__all__ = ["PhoneLockedError", "open_run_door"]
